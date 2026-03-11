"""Tests for patient-case parsing and biomedical entity extraction."""

import json
from pathlib import Path
from github_viz.analysis.parser import (
    build_extraction_dictionary,
    extract_entities,
    parse_patient_case,
)

# Minimal test fixture
TEST_ENTITIES = {
    "diseases": [
        {
            "id": "disease:parkinson",
            "label": "Parkinson's disease",
            "aliases": ["Parkinson disease", "PD"],
        },
        {
            "id": "disease:diabetes",
            "label": "Type 2 diabetes",
            "aliases": ["T2DM", "diabetes mellitus"],
        },
    ],
    "symptoms": [
        {"id": "symptom:tremor", "label": "Tremor", "aliases": []},
        {"id": "symptom:rigidity", "label": "Rigidity", "aliases": []},
    ],
    "biomarkers": [
        {
            "id": "biomarker:crp",
            "label": "Elevated inflammation",
            "aliases": ["CRP", "C-reactive protein"],
        },
        {
            "id": "biomarker:microglia",
            "label": "Microglial activation",
            "aliases": ["activated microglia"],
        },
    ],
    "medications": [
        {"id": "drug:metformin", "label": "Metformin", "aliases": []},
    ],
    "genes": [],
    "proteins": [],
    "pathways": [],
}


def test_extract_entities_from_narrative():
    dictionary = build_extraction_dictionary(TEST_ENTITIES)
    report = "Patient with Parkinson disease and elevated CRP."

    entities = extract_entities(report, dictionary)

    assert "Parkinson's disease" in entities["diseases"]
    assert "Elevated inflammation" in entities["biomarkers"]


def test_parse_patient_case_merges_structured_and_narrative_terms():
    dictionary = build_extraction_dictionary(TEST_ENTITIES)
    patient_case = {
        "patient_id": "case-123",
        "age_range": "60-69",
        "sex": "female",
        "diagnoses": ["Parkinson's disease"],
        "symptoms": ["Tremor"],
        "biomarkers": [],
        "medications": [],
    }

    parsed = parse_patient_case(
        patient_case,
        "Narrative mentions elevated CRP.",
        dictionary,
    )

    assert parsed.patient_id == "case-123"
    assert parsed.diagnoses == ["Parkinson's disease"]
    assert "Elevated inflammation" in parsed.biomarkers
    assert "Tremor" in parsed.symptoms


def test_patient_summary_is_human_readable():
    dictionary = build_extraction_dictionary(TEST_ENTITIES)
    parsed = parse_patient_case(
        {
            "patient_id": "case-001",
            "age_range": "70-79",
            "sex": "male",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Rigidity"],
            "biomarkers": ["Elevated inflammation"],
            "medications": [],
        },
        "",
        dictionary,
    )

    summary = parsed.patient_summary()
    assert "70-79 male" in summary
    assert "Parkinson's disease" in summary
