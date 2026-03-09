"""Evidence provider adapters and registry helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from github_viz.analysis.graph import DATA_FILE
from github_viz.config import Settings


@dataclass(frozen=True)
class ProviderMetadata:
    """Metadata describing a configured evidence provider."""

    provider_id: str
    version: str
    description: str
    kind: str
    location: str

    def to_dict(self) -> dict[str, str]:
        return {
            "provider_id": self.provider_id,
            "version": self.version,
            "description": self.description,
            "kind": self.kind,
            "location": self.location,
        }


class EvidenceProvider:
    """Abstract evidence provider."""

    def describe(self) -> ProviderMetadata:
        raise NotImplementedError

    def load(self) -> dict[str, Any]:
        raise NotImplementedError


class JsonFileEvidenceProvider(EvidenceProvider):
    """JSON-backed evidence provider using the project seed schema."""

    def __init__(
        self,
        path: str | Path,
        *,
        provider_id: str | None = None,
        description: str | None = None,
        kind: str = "json_file",
    ) -> None:
        self.path = Path(path)
        self._provider_id = provider_id
        self._description = description
        self._kind = kind

    def describe(self) -> ProviderMetadata:
        payload = self._load_json()
        provider_id = self._provider_id or str(payload.get("provider_id") or self.path.stem)
        version = str(payload.get("version", "unknown"))
        description = self._description or str(
            payload.get("description") or f"Evidence provider loaded from {self.path.name}."
        )
        return ProviderMetadata(
            provider_id=provider_id,
            version=version,
            description=description,
            kind=self._kind,
            location=str(self.path),
        )

    def load(self) -> dict[str, Any]:
        payload = self._load_json()
        metadata = self.describe()
        normalized = {
            "provider_id": metadata.provider_id,
            "version": metadata.version,
            "description": metadata.description,
            "entities": payload.get("entities", {}),
            "papers": [],
            "relationships": payload.get("relationships", {}),
        }
        for paper in payload.get("papers", []):
            paper_copy = dict(paper)
            paper_copy.setdefault("provider_id", metadata.provider_id)
            normalized["papers"].append(paper_copy)
        return normalized

    def _load_json(self) -> dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


class CuratedSeedProvider(JsonFileEvidenceProvider):
    """Bundled curated evidence provider."""

    def __init__(self) -> None:
        super().__init__(
            DATA_FILE,
            provider_id="curated_seed",
            description="Curated biomedical baseline dataset bundled with the repository.",
            kind="bundled_seed",
        )


def build_provider_registry(settings: Settings) -> list[EvidenceProvider]:
    """Build the configured provider list for the current runtime."""
    providers: list[EvidenceProvider] = [CuratedSeedProvider()]
    for raw_path in settings.extra_provider_paths:
        path = Path(raw_path)
        if not path.exists():
            continue
        providers.append(JsonFileEvidenceProvider(path))
    return providers


def dataset_versions(
    providers: list[EvidenceProvider],
    *,
    evidence_mode: str = "hybrid",
) -> list[dict[str, str]]:
    """Return metadata for providers participating in a given evidence mode."""
    return [provider.describe().to_dict() for provider in active_providers(providers, evidence_mode=evidence_mode)]


def load_evidence_bundle(
    providers: list[EvidenceProvider],
    *,
    evidence_mode: str = "hybrid",
) -> dict[str, Any]:
    """Load and merge evidence from the active providers."""
    active = active_providers(providers, evidence_mode=evidence_mode)
    bundles = [provider.load() for provider in active]
    merged = merge_evidence_bundles(bundles)
    merged["version"] = "+".join(bundle.get("version", "unknown") for bundle in bundles) or "unknown"
    merged["providers"] = [provider.describe().to_dict() for provider in active]
    return merged


def active_providers(providers: list[EvidenceProvider], *, evidence_mode: str) -> list[EvidenceProvider]:
    """Resolve which providers participate for the current evidence mode."""
    if evidence_mode == "offline":
        return providers[:1]
    return providers


def merge_evidence_bundles(bundles: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge multiple seed-shaped evidence bundles into one deterministic dataset."""
    merged: dict[str, Any] = {
        "entities": {},
        "papers": [],
        "relationships": {},
    }

    entity_seen: dict[str, set[str]] = {}
    paper_seen: set[str] = set()
    relationship_seen: dict[str, set[str]] = {}

    for bundle in bundles:
        for bucket, items in bundle.get("entities", {}).items():
            entity_seen.setdefault(bucket, set())
            target = merged["entities"].setdefault(bucket, [])
            for item in items:
                key = str(item.get("id") or item.get("label") or json.dumps(item, sort_keys=True))
                if key in entity_seen[bucket]:
                    continue
                entity_seen[bucket].add(key)
                target.append(item)

        for paper in bundle.get("papers", []):
            key = str(paper.get("id") or json.dumps(paper, sort_keys=True))
            if key in paper_seen:
                continue
            paper_seen.add(key)
            merged["papers"].append(paper)

        for relation_type, items in bundle.get("relationships", {}).items():
            relationship_seen.setdefault(relation_type, set())
            target = merged["relationships"].setdefault(relation_type, [])
            for item in items:
                key = json.dumps(item, sort_keys=True)
                if key in relationship_seen[relation_type]:
                    continue
                relationship_seen[relation_type].add(key)
                target.append(item)

    return merged
