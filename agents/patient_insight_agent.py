"""Patient Insight Agent — extracts structured biomedical entities from a patient record.

This agent reads either a raw FHIR-formatted JSON record or a structured
dict and produces a normalized entity bag that downstream agents and the
Cure Graph builder can consume.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PatientInsight:
    """Output of the Patient Insight Agent."""

    patient_id: str
    age_range: str = "unknown"
    sex: str = "unknown"
    diagnoses: list[str] = field(default_factory=list)
    symptoms: list[str] = field(default_factory=list)
    biomarkers: list[str] = field(default_factory=list)
    medications: list[str] = field(default_factory=list)
    report_text: str = ""
    confidence: float = 1.0
    source: str = "structured"

    def to_patient_case(self) -> dict[str, Any]:
        """Convert to the dict format expected by ``analyze_case``."""
        return {
            "patient_id": self.patient_id,
            "age_range": self.age_range,
            "sex": self.sex,
            "diagnoses": list(self.diagnoses),
            "symptoms": list(self.symptoms),
            "biomarkers": list(self.biomarkers),
            "medications": list(self.medications),
        }


def extract_patient_insight(
    patient_data: dict[str, Any],
    *,
    source: str = "structured",
) -> PatientInsight:
    """Extract entities from a patient record.

    Accepts either a raw FHIR-style dict (with ``resourceType``) or
    the simpler ``PatientCase`` dict used by the API.
    """
    # Detect FHIR format
    if patient_data.get("resourceType") == "Patient":
        return _extract_from_fhir(patient_data)

    return _extract_from_structured(patient_data, source=source)


def _extract_from_structured(data: dict[str, Any], source: str = "structured") -> PatientInsight:
    """Parse the flat PatientCase dict."""
    return PatientInsight(
        patient_id=str(data.get("patient_id", "patient-record")),
        age_range=str(data.get("age_range", data.get("age", "unknown"))),
        sex=str(data.get("sex", "unknown")),
        diagnoses=_as_list(data.get("diagnoses", data.get("condition", []))),
        symptoms=_as_list(data.get("symptoms", [])),
        biomarkers=_as_list(data.get("biomarkers", data.get("observations", []))),
        medications=_as_list(data.get("medications", [])),
        report_text=str(data.get("report_text", "")),
        source=source,
    )


def _extract_from_fhir(fhir_record: dict[str, Any]) -> PatientInsight:
    """Parse a FHIR Patient-style record.

    The FHIR standard is complex; this parser handles our simplified
    local format as well as the most common fields from a real
    FHIR Patient + Condition + Observation bundle.
    """
    patient_id = fhir_record.get("id", "fhir-patient")

    # Age from birthDate or explicit field
    age_range = str(fhir_record.get("age_range", fhir_record.get("age", "unknown")))

    # Sex
    sex = str(fhir_record.get("gender", fhir_record.get("sex", "unknown")))

    # Conditions / diagnoses
    conditions = fhir_record.get("condition", [])
    if isinstance(conditions, str):
        conditions = [conditions]
    diagnoses: list[str] = []
    for cond in conditions:
        if isinstance(cond, dict):
            code = cond.get("code", {})
            if isinstance(code, dict):
                diagnoses.append(code.get("text", code.get("display", str(cond))))
            else:
                diagnoses.append(str(code))
        else:
            diagnoses.append(str(cond))

    # Observations → biomarkers
    observations = fhir_record.get("observations", [])
    if isinstance(observations, str):
        observations = [observations]
    biomarkers: list[str] = []
    for obs in observations:
        if isinstance(obs, dict):
            biomarkers.append(obs.get("display", obs.get("text", str(obs))))
        else:
            biomarkers.append(str(obs))

    # Medications
    meds = fhir_record.get("medications", fhir_record.get("medicationRequest", []))
    if isinstance(meds, str):
        meds = [meds]
    medications: list[str] = []
    for med in meds:
        if isinstance(med, dict):
            medications.append(med.get("display", med.get("text", str(med))))
        else:
            medications.append(str(med))

    # Symptoms are not standard on Patient resources but may appear in local inputs.
    symptoms = _as_list(fhir_record.get("symptoms", []))

    logger.info(
        "FHIR extraction: patient_id=%s diagnoses=%d biomarkers=%d medications=%d",
        patient_id,
        len(diagnoses),
        len(biomarkers),
        len(medications),
    )

    return PatientInsight(
        patient_id=patient_id,
        age_range=age_range,
        sex=sex,
        diagnoses=diagnoses,
        symptoms=symptoms,
        biomarkers=biomarkers,
        medications=medications,
        source="fhir",
    )


def _as_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []
