"""Patient-case parsing and lightweight biomedical entity extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable


@dataclass
class ParsedPatientCase:
    """Normalized patient case used by the Cure Graph builder."""

    patient_id: str
    age_range: str
    sex: str
    diagnoses: list[str]
    symptoms: list[str]
    biomarkers: list[str]
    medications: list[str]
    report_text: str = ""
    narrative_entities: dict[str, list[str]] = field(default_factory=dict)

    def all_terms(self) -> list[str]:
        items = [*self.diagnoses, *self.symptoms, *self.biomarkers, *self.medications]
        if self.report_text:
            items.extend(self.narrative_entities.get("diseases", []))
            items.extend(self.narrative_entities.get("symptoms", []))
            items.extend(self.narrative_entities.get("biomarkers", []))
            items.extend(self.narrative_entities.get("medications", []))
        return _dedupe_preserve_order(items)

    def patient_summary(self) -> str:
        parts = [f"{self.age_range} {self.sex}".strip()]
        if self.diagnoses:
            parts.append(f"diagnoses: {', '.join(self.diagnoses)}")
        if self.symptoms:
            parts.append(f"symptoms: {', '.join(self.symptoms)}")
        if self.biomarkers:
            parts.append(f"biomarkers: {', '.join(self.biomarkers)}")
        if self.medications:
            parts.append(f"medications: {', '.join(self.medications)}")
        return "; ".join(part for part in parts if part)


@dataclass
class ExtractionDictionary:
    """Lookup tables used for narrative entity extraction."""

    diseases: dict[str, list[str]] = field(default_factory=dict)
    symptoms: dict[str, list[str]] = field(default_factory=dict)
    biomarkers: dict[str, list[str]] = field(default_factory=dict)
    medications: dict[str, list[str]] = field(default_factory=dict)


def parse_patient_case(patient_case: dict, report_text: str, dictionary: ExtractionDictionary) -> ParsedPatientCase:
    """Normalize structured patient data and extract entities from free text."""
    narrative_entities = extract_entities(report_text, dictionary) if report_text else {}

    diagnoses = merge_terms(patient_case.get("diagnoses", []), narrative_entities.get("diseases", []))
    symptoms = merge_terms(patient_case.get("symptoms", []), narrative_entities.get("symptoms", []))
    biomarkers = merge_terms(patient_case.get("biomarkers", []), narrative_entities.get("biomarkers", []))
    medications = merge_terms(patient_case.get("medications", []), narrative_entities.get("medications", []))

    return ParsedPatientCase(
        patient_id=str(patient_case.get("patient_id") or "patient-record").strip() or "patient-record",
        age_range=str(patient_case.get("age_range") or "unknown").strip() or "unknown",
        sex=str(patient_case.get("sex") or "unknown").strip() or "unknown",
        diagnoses=diagnoses,
        symptoms=symptoms,
        biomarkers=biomarkers,
        medications=medications,
        report_text=report_text.strip(),
        narrative_entities=narrative_entities,
    )


def extract_entities(report_text: str, dictionary: ExtractionDictionary) -> dict[str, list[str]]:
    """Run deterministic alias matching over the narrative report."""
    text = report_text.casefold()
    extracted: dict[str, list[str]] = {}
    for bucket_name in ("diseases", "symptoms", "biomarkers", "medications"):
        matches: list[str] = []
        bucket = getattr(dictionary, bucket_name)
        for canonical, aliases in bucket.items():
            terms = [canonical, *aliases]
            for term in terms:
                if _contains_term(text, term):
                    matches.append(canonical)
                    break
        extracted[bucket_name] = _dedupe_preserve_order(matches)
    return extracted


def build_extraction_dictionary(seed_entities: dict[str, list[dict]]) -> ExtractionDictionary:
    """Build an alias dictionary from seeded biomedical entities."""
    def as_lookup(items: Iterable[dict]) -> dict[str, list[str]]:
        lookup: dict[str, list[str]] = {}
        for item in items:
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            lookup[label] = [str(alias).strip() for alias in item.get("aliases", []) if str(alias).strip()]
        return lookup

    return ExtractionDictionary(
        diseases=as_lookup(seed_entities.get("diseases", [])),
        symptoms=as_lookup(seed_entities.get("symptoms", [])),
        biomarkers=as_lookup(seed_entities.get("biomarkers", [])),
        medications=as_lookup(seed_entities.get("drugs", [])),
    )


def merge_terms(primary: list[str], secondary: list[str]) -> list[str]:
    """Merge user-entered and narrative-extracted terms without duplicates."""
    return _dedupe_preserve_order([*primary, *secondary])


def _contains_term(text: str, term: str) -> bool:
    normalized = re.escape(term.casefold())
    return re.search(rf"(?<![\w]){normalized}(?![\w])", text) is not None


def _dedupe_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        normalized = str(item).strip()
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result
