"""FHIR record parser — converts FHIR Patient bundles into PatientCase dicts.

This utility bridges the FHIR data format with the Agentic Cure Graph
pipeline. It handles both the simplified local format and common real
FHIR Patient/Condition/Observation resources.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any

logger = logging.getLogger(__name__)


def parse_fhir_file(file_path: str | pathlib.Path) -> dict[str, Any]:
    """Load a FHIR JSON file and convert it to a PatientCase dict."""
    path = pathlib.Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"FHIR file not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        fhir_record = json.load(f)

    return parse_fhir_record(fhir_record)


def parse_fhir_record(fhir_record: dict[str, Any]) -> dict[str, Any]:
    """Convert a FHIR Patient-style record into a PatientCase dict.

    Handles both the simplified local format and standard FHIR fields.
    Returns a dict compatible with the ``AnalyzeRequest`` schema.
    """
    resource_type = fhir_record.get("resourceType", "")
    if resource_type and resource_type != "Patient":
        logger.warning("Expected resourceType=Patient, got %s", resource_type)

    patient_id = fhir_record.get("id", "fhir-patient")
    gender = fhir_record.get("gender", "unknown")
    age_range = fhir_record.get("age_range", "unknown")

    # Extract diagnoses from conditions
    diagnoses = _extract_diagnoses(fhir_record)

    # Extract biomarkers from observations
    biomarkers = _extract_observations(fhir_record)

    # Extract medications
    medications = _extract_medications(fhir_record)

    # Extract symptoms
    symptoms = _extract_list(fhir_record.get("symptoms", []))

    # Build report text from note if available
    report_text = fhir_record.get("note", "")
    if isinstance(report_text, list):
        report_text = " ".join(str(n) for n in report_text)

    patient_case = {
        "patient_id": patient_id,
        "age_range": age_range,
        "sex": gender,
        "diagnoses": diagnoses,
        "symptoms": symptoms,
        "biomarkers": biomarkers,
        "medications": medications,
    }

    logger.info(
        "Parsed FHIR record: patient_id=%s, diagnoses=%d, biomarkers=%d, medications=%d",
        patient_id,
        len(diagnoses),
        len(biomarkers),
        len(medications),
    )

    return {
        "patient_case": patient_case,
        "report_text": report_text,
        "evidence_mode": "offline",
        "with_ai": False,
        "ai": None,
    }


def _extract_diagnoses(record: dict[str, Any]) -> list[str]:
    """Extract diagnosis strings from FHIR condition field."""
    conditions = record.get("condition", [])
    if isinstance(conditions, str):
        return [conditions]

    diagnoses: list[str] = []
    for cond in conditions:
        if isinstance(cond, str):
            diagnoses.append(cond)
        elif isinstance(cond, dict):
            code = cond.get("code", {})
            if isinstance(code, dict):
                text = code.get("text") or code.get("display") or ""
                if text:
                    diagnoses.append(str(text))
            elif code:
                diagnoses.append(str(code))
    return diagnoses


def _extract_observations(record: dict[str, Any]) -> list[str]:
    """Extract biomarker strings from FHIR observations field."""
    observations = record.get("observations", [])
    if isinstance(observations, str):
        return [observations]

    biomarkers: list[str] = []
    for obs in observations:
        if isinstance(obs, str):
            biomarkers.append(obs)
        elif isinstance(obs, dict):
            display = obs.get("display") or obs.get("text") or ""
            if display:
                biomarkers.append(str(display))
    return biomarkers


def _extract_medications(record: dict[str, Any]) -> list[str]:
    """Extract medication strings from FHIR medications field."""
    meds = record.get("medications", record.get("medicationRequest", []))
    if isinstance(meds, str):
        return [meds]

    medications: list[str] = []
    for med in meds:
        if isinstance(med, str):
            medications.append(med)
        elif isinstance(med, dict):
            display = med.get("display") or med.get("text") or ""
            if display:
                medications.append(str(display))
    return medications


def _extract_list(value: Any) -> list[str]:
    """Normalize a field to a list of strings."""
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []
