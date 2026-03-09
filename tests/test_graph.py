"""Tests for Cure Graph construction and analytics."""

from github_viz.analysis.graph import analyze_case
from github_viz.analysis.stats import compute_stats, find_shortest_path, search_nodes


def build_sample_graph():
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
        evidence_mode="hybrid",
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
    assert hypotheses[0]["label"] == "Metformin for Parkinson's disease"
    assert hypotheses[0]["score"] >= 0.7
    assert hypotheses[0]["evidence_count"] >= 3


def test_compute_stats_returns_biomedical_metrics():
    graph = build_sample_graph()
    stats = compute_stats(graph)

    assert stats["total_nodes"] >= 1
    assert stats["entity_counts"]["hypothesis"] >= 1
    assert stats["patient_profile"]["diagnosis_count"] == 1
    assert stats["evidence_coverage"]["paper_nodes"] >= 1
    assert stats["top_hypotheses"][0]["label"] == "Metformin for Parkinson's disease"


def test_shortest_path_connects_patient_to_supporting_paper():
    graph = build_sample_graph()
    path = find_shortest_path(
        graph,
        "patient:case-001",
        "paper:metformin-neuroinflammation-2023",
    )

    assert path is not None
    assert path[0] == "patient:case-001"
    assert path[-1] == "paper:metformin-neuroinflammation-2023"


def test_search_finds_biomarker_and_hypothesis():
    graph = build_sample_graph()
    biomarker_results = search_nodes(graph, "microglial")
    hypothesis_results = search_nodes(graph, "metformin")

    assert biomarker_results
    assert any(item["type"] == "biomarker" for item in biomarker_results)
    assert any(item["type"] == "hypothesis" for item in hypothesis_results)
