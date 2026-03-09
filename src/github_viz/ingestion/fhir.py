"""FHIR normalization helpers for Cure Graph requests."""

from __future__ import annotations

from typing import Any


def parse_fhir_record(fhir_record: dict[str, Any]) -> dict[str, Any]:
    """Convert a simplified FHIR-like record into the internal request shape."""
    patient_id = str(fhir_record.get("id") or "fhir-patient").strip() or "fhir-patient"
    gender = str(fhir_record.get("gender") or fhir_record.get("sex") or "unknown").strip() or "unknown"
    age_range = str(fhir_record.get("age_range") or fhir_record.get("age") or "unknown").strip() or "unknown"

    diagnoses = _extract_diagnoses(fhir_record)
    biomarkers = _extract_observations(fhir_record)
    medications = _extract_medications(fhir_record)
    symptoms = _extract_list(fhir_record.get("symptoms", []))

    report_text = fhir_record.get("note", "")
    if isinstance(report_text, list):
        report_text = " ".join(str(item).strip() for item in report_text if str(item).strip())
    report_text = str(report_text or "").strip()

    return {
        "patient_case": {
            "patient_id": patient_id,
            "age_range": age_range,
            "sex": gender,
            "diagnoses": diagnoses,
            "symptoms": symptoms,
            "biomarkers": biomarkers,
            "medications": medications,
        },
        "report_text": report_text,
        "evidence_mode": "offline",
        "with_ai": False,
        "ai": None,
    }


def _extract_diagnoses(record: dict[str, Any]) -> list[str]:
    conditions = record.get("condition", [])
    if isinstance(conditions, str):
        return [conditions] if conditions.strip() else []

    diagnoses: list[str] = []
    for condition in conditions:
        if isinstance(condition, str):
            value = condition.strip()
            if value:
                diagnoses.append(value)
            continue
        if not isinstance(condition, dict):
            continue
        code = condition.get("code", {})
        if isinstance(code, dict):
            value = code.get("text") or code.get("display") or ""
        else:
            value = str(code or "")
        value = str(value).strip()
        if value:
            diagnoses.append(value)
    return diagnoses


def _extract_observations(record: dict[str, Any]) -> list[str]:
    observations = record.get("observations", [])
    if isinstance(observations, str):
        return [observations] if observations.strip() else []

    biomarkers: list[str] = []
    for observation in observations:
        if isinstance(observation, str):
            value = observation.strip()
            if value:
                biomarkers.append(value)
            continue
        if not isinstance(observation, dict):
            continue
        value = observation.get("display") or observation.get("text") or ""
        value = str(value).strip()
        if value:
            biomarkers.append(value)
    return biomarkers


def _extract_medications(record: dict[str, Any]) -> list[str]:
    medications = record.get("medications", record.get("medicationRequest", []))
    if isinstance(medications, str):
        return [medications] if medications.strip() else []

    values: list[str] = []
    for medication in medications:
        if isinstance(medication, str):
            value = medication.strip()
            if value:
                values.append(value)
            continue
        if not isinstance(medication, dict):
            continue
        value = medication.get("display") or medication.get("text") or ""
        value = str(value).strip()
        if value:
            values.append(value)
    return values


def _extract_list(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.strip()
        return [normalized] if normalized else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
