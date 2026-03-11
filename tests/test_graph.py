"""Tests for Cure Graph construction and analytics."""

import json
from pathlib import Path
from uuid import uuid4

from github_viz.config import Settings
from github_viz.providers import build_provider_registry

from github_viz.analysis.graph import analyze_case
from github_viz.analysis.stats import compute_stats, find_shortest_path, search_nodes

TEST_VAR_DIR = Path(__file__).resolve().parents[1] / "var_test"


def _test_overlay_path() -> Path:
    """Create a test overlay for graph tests."""
    TEST_VAR_DIR.mkdir(exist_ok=True)
    path = TEST_VAR_DIR / f"graph-test-{uuid4().hex}.json"
    payload = {
        "provider_id": "test_provider",
        "version": "2026.03-test",
        "description": "Test data for graph tests",
        "entities": {
            "drugs": [
                {"id": "drug:metformin", "label": "Metformin"},
                {"id": "drug:pioglitazone", "label": "Pioglitazone"},
            ],
            "diseases": [
                {"id": "disease:parkinson", "label": "Parkinson's disease"},
                {"id": "disease:diabetes", "label": "Type 2 diabetes"},
            ],
        },
        "papers": [
            {
                "id": "paper:metformin-neuroinflammation-2023",
                "title": "Metformin and neuroinflammation in Parkinson's disease",
                "journal": "Neurology",
                "year": 2023,
                "citation": "Neurology (2023)",
                "abstract_snippet": "Metformin showed anti-inflammatory effects in Parkinsonian models.",
                "entities": ["Metformin", "Parkinson's disease", "Neuroinflammation"],
            }
        ],
        "relationships": {
            "drug_hypotheses": [
                {
                    "drug": "Metformin",
                    "disease": "Parkinson's disease",
                    "mechanism": "Metformin may reduce neuroinflammation via AMPK pathway.",
                    "biomarker_matches": ["Elevated inflammation"],
                    "genes": ["PRKAA1"],
                    "proteins": ["AMPK"],
                    "pathways": ["AMPK pathway"],
                    "papers": ["paper:metformin-neuroinflammation-2023"],
                }
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def build_sample_graph():
    """Build sample graph using offline mode with test overlay."""
    overlay = _test_overlay_path()
    settings = Settings(extra_provider_paths=(str(overlay),))
    providers = build_provider_registry(settings)

    # Get evidence bundle from providers
    from github_viz.providers import load_evidence_bundle

    evidence_bundle = load_evidence_bundle(providers, evidence_mode="offline")

    return analyze_case(
        patient_case={
            "patient_id": "case-001",
            "age_range": "60-69",
            "sex": "female",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Tremor"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        },
        report_text="Narrative mentions activated microglia and elevated CRP in a Parkinson disease patient.",
        evidence_mode="offline",
        evidence_bundle=evidence_bundle,
        with_ai=False,
    )


def test_analyze_case_builds_patient_and_hypothesis_nodes():
    graph = build_sample_graph()
    node_types = {node["type"] for node in graph["nodes"]}

    assert "patient" in node_types
    assert "hypothesis" in node_types
    assert "research_paper" in node_types
    assert graph["meta"]["hypothesis_count"] >= 1


def test_metformin_hypothesis_is_ranked():
    graph = build_sample_graph()
    hypotheses = sorted(
        [node for node in graph["nodes"] if node["type"] == "hypothesis"],
        key=lambda item: item["score"],
        reverse=True,
    )

    assert hypotheses
    assert "Metformin for Parkinson's disease" in hypotheses[0]["label"]
    assert hypotheses[0]["score"] >= 0.5


def test_compute_stats_returns_biomedical_metrics():
    graph = build_sample_graph()
    stats = compute_stats(graph)

    assert stats["total_nodes"] >= 1
    assert stats["entity_counts"]["hypothesis"] >= 1
    assert stats["patient_profile"]["diagnosis_count"] >= 1
    assert stats["evidence_coverage"]["paper_nodes"] >= 1


def test_shortest_path_connects_patient_to_supporting_paper():
    graph = build_sample_graph()
    path = find_shortest_path(
        graph,
        "patient:case-001",
        "paper:metformin-neuroinflammation-2023",
    )

    assert path is not None
    assert path[0] == "patient:case-001"
    assert "paper:metformin-neuroinflammation-2023" in path[-1]


def test_search_finds_biomarker_and_hypothesis():
    graph = build_sample_graph()
    biomarker_results = search_nodes(graph, "inflammation")
    hypothesis_results = search_nodes(graph, "metformin")

    assert biomarker_results
    assert any(
        item["type"] in ["biomarker", "hypothesis"] for item in biomarker_results
    )
    assert any(item["type"] == "hypothesis" for item in hypothesis_results)
