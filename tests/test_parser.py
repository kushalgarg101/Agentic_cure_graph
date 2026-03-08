"""Tests for patient-case parsing and biomedical entity extraction."""

from github_viz.analysis.graph import load_seed_data
from github_viz.analysis.parser import build_extraction_dictionary, extract_entities, parse_patient_case


def test_extract_entities_from_narrative():
    seed = load_seed_data()
    dictionary = build_extraction_dictionary(seed["entities"])
    report = "Patient with Parkinson disease, elevated CRP, activated microglia, and metformin exposure."

    entities = extract_entities(report, dictionary)

    assert "Parkinson's disease" in entities["diseases"]
    assert "Elevated inflammation" in entities["biomarkers"]
    assert "Microglial activation" in entities["biomarkers"]
    assert "Metformin" in entities["medications"]


def test_parse_patient_case_merges_structured_and_narrative_terms():
    seed = load_seed_data()
    dictionary = build_extraction_dictionary(seed["entities"])
    patient_case = {
        "patient_id": "demo-123",
        "age_range": "60-69",
        "sex": "female",
        "diagnoses": ["Parkinson's disease"],
        "symptoms": ["Tremor"],
        "biomarkers": [],
        "medications": [],
    }

    parsed = parse_patient_case(
        patient_case,
        "Narrative notes mention elevated CRP and activated microglia while the patient remains on Metformin.",
        dictionary,
    )

    assert parsed.patient_id == "demo-123"
    assert parsed.diagnoses == ["Parkinson's disease"]
    assert "Elevated inflammation" in parsed.biomarkers
    assert "Microglial activation" in parsed.biomarkers
    assert "Metformin" in parsed.medications
    assert "Tremor" in parsed.symptoms


def test_patient_summary_is_human_readable():
    seed = load_seed_data()
    dictionary = build_extraction_dictionary(seed["entities"])
    parsed = parse_patient_case(
        {
            "patient_id": "demo-001",
            "age_range": "70-79",
            "sex": "male",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Rigidity"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        },
        "",
        dictionary,
    )

    summary = parsed.patient_summary()
    assert "70-79 male" in summary
    assert "Parkinson's disease" in summary
    assert "Metformin" in summary
