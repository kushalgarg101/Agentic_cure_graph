"""Hypothesis Agent — generates and ranks treatment hypotheses from the Cure Graph.

This agent wraps the hardened backend service and exposes ranked hypotheses
for A2A communication, MCP tool calls, and backend integrations.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

from github_viz.config import Settings, get_settings
from github_viz.providers import EvidenceProvider, build_provider_registry
from github_viz.services import collect_hypotheses, run_analysis

logger = logging.getLogger(__name__)


@dataclass
class RankedHypothesis:
    """A single scored hypothesis from the Cure Graph."""

    hypothesis_id: str
    label: str
    score: float
    mechanism: str = ""
    rationale: str = ""
    evidence_count: int = 0
    supporting_paper_ids: list[str] = field(default_factory=list)
    biomarker_overlap: list[str] = field(default_factory=list)
    classification: str = "insufficient_evidence"
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.hypothesis_id,
            "label": self.label,
            "score": round(self.score, 3),
            "mechanism": self.mechanism,
            "rationale": self.rationale,
            "evidence_count": self.evidence_count,
            "supporting_paper_ids": self.supporting_paper_ids,
            "biomarker_overlap": self.biomarker_overlap,
            "classification": self.classification,
            "provenance": self.provenance,
        }


@dataclass
class HypothesisResult:
    """Output of the Hypothesis Agent."""

    session_id: str
    patient_summary: str
    hypotheses: list[RankedHypothesis]
    graph: dict[str, Any]
    analysis_time_s: float = 0.0
    warnings: list[str] = field(default_factory=list)
    dataset_versions: list[dict[str, Any]] = field(default_factory=list)
    policy: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "patient_summary": self.patient_summary,
            "hypothesis_count": len(self.hypotheses),
            "analysis_time_s": self.analysis_time_s,
            "warnings": self.warnings,
            "dataset_versions": self.dataset_versions,
            "policy": self.policy,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
        }


def generate_hypotheses(
    patient_case: dict[str, Any],
    *,
    report_text: str = "",
    evidence_mode: str = "offline",
    with_ai: bool = False,
    ai_options: dict[str, Any] | None = None,
    settings: Settings | None = None,
    providers: list[EvidenceProvider] | None = None,
    analysis_id: str | None = None,
) -> HypothesisResult:
    """Run the Cure Graph pipeline and return ranked hypotheses.

    This is the main entry point for the Hypothesis Agent. It uses the
    same provider-aware analysis service as the main FastAPI backend.
    """
    logger.info("Hypothesis Agent: generating hypotheses for patient=%s", patient_case.get("patient_id"))

    resolved_settings = settings or get_settings()
    resolved_providers = providers or build_provider_registry(resolved_settings)
    resolved_analysis_id = analysis_id or str(uuid.uuid4())

    result = run_analysis(
        analysis_id=resolved_analysis_id,
        patient_case=patient_case,
        report_text=report_text,
        evidence_mode=evidence_mode,
        with_ai=with_ai,
        ai_options=ai_options,
        providers=resolved_providers,
    )
    graph = result["graph"]
    meta = graph.get("meta", {})
    hypothesis_nodes = collect_hypotheses(graph)

    hypotheses = [
        RankedHypothesis(
            hypothesis_id=n["id"],
            label=n.get("label", ""),
            score=float(n.get("score", 0.0)),
            mechanism=n.get("summary", ""),
            rationale=n.get("meta", {}).get("rationale", ""),
            evidence_count=int(n.get("evidence_count", 0)),
            supporting_paper_ids=n.get("meta", {}).get("supporting_paper_ids", []),
            biomarker_overlap=n.get("meta", {}).get("biomarker_overlap", []),
            classification=n.get("classification", "insufficient_evidence"),
            provenance=n.get("provenance", {}),
        )
        for n in hypothesis_nodes
    ]

    patient_node = next((n for n in graph.get("nodes", []) if n.get("type") == "patient"), {})

    logger.info(
        "Hypothesis Agent: found %d hypotheses in %.2fs",
        len(hypotheses),
        meta.get("analysis_time_s", 0),
    )

    return HypothesisResult(
        session_id=meta.get("session_id", ""),
        patient_summary=patient_node.get("summary", ""),
        hypotheses=hypotheses,
        graph=graph,
        analysis_time_s=meta.get("analysis_time_s", 0),
        warnings=result.get("warnings", []),
        dataset_versions=result.get("dataset_versions", []),
        policy=result.get("policy", {}),
    )
