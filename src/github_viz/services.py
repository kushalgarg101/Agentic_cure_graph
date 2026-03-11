"""Service helpers for durable analysis workflows."""

from __future__ import annotations

from typing import Any

from github_viz.analysis.graph import analyze_case
from github_viz.analysis.stats import compute_stats
from github_viz.providers import (
    EvidenceProvider,
    dataset_versions,
    load_evidence_bundle,
)

POLICY_VERSION = "2026-03-09"
INTENDED_USE = "clinician_research_assistant"


def run_analysis(
    *,
    analysis_id: str,
    patient_case: dict[str, Any],
    report_text: str,
    evidence_mode: str,
    with_ai: bool,
    ai_options: dict[str, Any] | None,
    providers: list[EvidenceProvider],
) -> dict[str, Any]:
    # In hybrid mode, let analyze_case fetch from APIs directly
    # In offline mode, load evidence bundle from providers
    fetch_from_apis = evidence_mode == "hybrid"

    if fetch_from_apis:
        # Let analyze_case handle API fetching
        evidence_bundle = None
    else:
        # Load from providers (offline mode)
        evidence_bundle = load_evidence_bundle(providers, evidence_mode=evidence_mode)

    provider_versions = dataset_versions(providers, evidence_mode=evidence_mode)
    graph = analyze_case(
        patient_case=patient_case,
        report_text=report_text,
        evidence_mode=evidence_mode,
        with_ai=with_ai,
        ai_options=ai_options,
        evidence_bundle=evidence_bundle,
        fetch_from_apis=fetch_from_apis,
    )
    graph.setdefault("meta", {})
    graph["meta"]["analysis_id"] = analysis_id
    graph["meta"]["session_id"] = analysis_id
    graph["meta"]["policy"] = build_policy()
    graph["meta"]["dataset_versions"] = provider_versions
    graph["meta"]["warnings"] = build_warnings(graph)
    graph["meta"]["source_provenance"] = build_source_provenance(
        graph, provider_versions
    )
    graph["meta"]["input_quality"] = classify_input_quality(
        patient_case, graph["meta"]["warnings"]
    )
    stats = compute_stats(graph)
    return {
        "graph": graph,
        "stats": stats,
        "warnings": graph["meta"]["warnings"],
        "policy": graph["meta"]["policy"],
        "dataset_versions": graph["meta"]["dataset_versions"],
        "source_provenance": graph["meta"]["source_provenance"],
        "input_quality": graph["meta"]["input_quality"],
    }


def build_policy() -> dict[str, Any]:
    return {
        "version": POLICY_VERSION,
        "intended_use": INTENDED_USE,
        "not_for_diagnostic_use": True,
        "autonomous_recommendation": False,
        "evidence_policy": "curated_baseline_with_optional_pluggable_enrichment",
    }


def build_warnings(graph: dict[str, Any]) -> list[str]:
    patient = next(
        (node for node in graph.get("nodes", []) if node.get("type") == "patient"), {}
    )
    warnings: list[str] = []
    diagnoses = patient.get("meta", {}).get("diagnoses", [])
    biomarkers = patient.get("meta", {}).get("biomarkers", [])
    hypothesis_count = int(graph.get("meta", {}).get("hypothesis_count", 0))
    provider_count = len(graph.get("meta", {}).get("dataset_versions", []))

    if not diagnoses:
        warnings.append(
            "No diagnosis was provided; downstream evidence matching will be limited."
        )
    if not biomarkers:
        warnings.append(
            "No biomarkers were provided; hypothesis ranking may be weaker."
        )
    if hypothesis_count == 0:
        warnings.append(
            "No supported hypotheses were found in the currently configured evidence sources."
        )
    if hypothesis_count > 0 and len(graph.get("nodes", [])) < 6:
        warnings.append(
            "Graph coverage is sparse for this case; review evidence provenance before use."
        )
    if provider_count == 1:
        warnings.append(
            "Only the bundled curated evidence provider was used for this analysis."
        )
    return warnings


def build_source_provenance(
    graph: dict[str, Any],
    provider_versions: list[dict[str, str]],
) -> list[dict[str, Any]]:
    paper_provider_index = {
        node.get("id"): {
            "provider": node.get("meta", {}).get("provider_id", "unknown"),
            "dataset_version": _provider_version(
                node.get("meta", {}).get("provider_id", "unknown"), provider_versions
            ),
        }
        for node in graph.get("nodes", [])
        if node.get("type") == "research_paper"
    }

    provenance: list[dict[str, Any]] = []
    for node in graph.get("nodes", []):
        if node.get("type") != "hypothesis":
            continue
        evidence_ids = node.get("meta", {}).get("supporting_paper_ids", [])
        providers = sorted(
            {
                paper_provider_index.get(evidence_id, {}).get("provider", "unknown")
                for evidence_id in evidence_ids
            }
        )
        provenance.append(
            {
                "hypothesis_id": node.get("id"),
                "providers": providers,
                "dataset_versions": {
                    provider: _provider_version(provider, provider_versions)
                    for provider in providers
                },
                "evidence_ids": evidence_ids,
            }
        )
    return provenance


def collect_hypotheses(graph: dict[str, Any]) -> list[dict[str, Any]]:
    provenance_index = {
        item["hypothesis_id"]: item
        for item in graph.get("meta", {}).get("source_provenance", [])
    }
    policy = graph.get("meta", {}).get("policy", build_policy())
    items = sorted(
        [node for node in graph.get("nodes", []) if node.get("type") == "hypothesis"],
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )
    for item in items:
        item.setdefault("classification", classify_hypothesis(item))
        item.setdefault(
            "limitations",
            build_hypothesis_limitations(
                item, graph.get("meta", {}).get("warnings", [])
            ),
        )
        item.setdefault("score_components", build_score_components(item))
        item.setdefault("provenance", provenance_index.get(item.get("id"), {}))
        item.setdefault("policy", policy)
    return items


def collect_evidence(graph: dict[str, Any]) -> list[dict[str, Any]]:
    papers_by_id = {
        node["id"]: node
        for node in graph.get("nodes", [])
        if node.get("type") == "research_paper"
    }
    evidence_items: list[dict[str, Any]] = []
    for hypothesis in collect_hypotheses(graph):
        paper_ids = hypothesis.get("meta", {}).get("supporting_paper_ids", [])
        papers = []
        for paper_id in paper_ids:
            paper = papers_by_id.get(paper_id)
            if not paper:
                continue
            papers.append(
                {
                    "id": paper_id,
                    "title": paper.get("label", ""),
                    "summary": paper.get("summary", ""),
                    "journal": paper.get("meta", {}).get("journal", ""),
                    "year": paper.get("meta", {}).get("year", ""),
                    "citation": paper.get("meta", {}).get("citation", ""),
                    "provider_id": paper.get("meta", {}).get("provider_id", "unknown"),
                }
            )
        evidence_items.append(
            {
                "hypothesis_id": hypothesis.get("id"),
                "label": hypothesis.get("label"),
                "classification": hypothesis.get("classification"),
                "evidence_count": len(papers),
                "papers": papers,
                "matched_entities": {
                    "biomarker_overlap": hypothesis.get("meta", {}).get(
                        "biomarker_overlap", []
                    ),
                    "disease": hypothesis.get("meta", {}).get("disease", ""),
                    "drug": hypothesis.get("meta", {}).get("drug", ""),
                },
                "provenance": hypothesis.get("provenance", {}),
            }
        )
    return evidence_items


def classify_hypothesis(hypothesis: dict[str, Any]) -> str:
    score = float(hypothesis.get("score", 0.0))
    evidence_count = int(hypothesis.get("evidence_count", 0))
    if evidence_count >= 3 and score >= 0.75:
        return "supported"
    if evidence_count >= 1 and score >= 0.5:
        return "exploratory"
    return "insufficient_evidence"


def build_hypothesis_limitations(
    hypothesis: dict[str, Any], warnings: list[str]
) -> list[str]:
    limitations = list(warnings)
    if int(hypothesis.get("evidence_count", 0)) < 3:
        limitations.append("Supporting paper count is limited for this hypothesis.")
    if not hypothesis.get("meta", {}).get("biomarker_overlap", []):
        limitations.append("No biomarker overlap was matched for this hypothesis.")
    return limitations


def build_score_components(hypothesis: dict[str, Any]) -> dict[str, Any]:
    meta = hypothesis.get("meta", {})
    paper_count = len(meta.get("supporting_paper_ids", []))
    biomarker_count = len(meta.get("biomarker_overlap", []))
    gene_count = int(meta.get("evidence_breakdown", {}).get("gene_count", 0))
    pathway_count = int(meta.get("evidence_breakdown", {}).get("pathway_count", 0))
    return {
        "paper_support": round(min(0.24, paper_count * 0.08), 3),
        "biomarker_overlap": round(min(0.18, biomarker_count * 0.09), 3),
        "pathway_support": round(min(0.12, pathway_count * 0.04), 3),
        "gene_support": round(min(0.1, gene_count * 0.03), 3),
        "base": 0.35,
        "total": round(float(hypothesis.get("score", 0.0)), 3),
    }


def classify_input_quality(patient_case: dict[str, Any], warnings: list[str]) -> str:
    populated = sum(
        1
        for field in ("diagnoses", "symptoms", "biomarkers", "medications")
        if patient_case.get(field)
    )
    if populated >= 3 and len(warnings) <= 1:
        return "high"
    if populated >= 2:
        return "medium"
    return "low"


def _provider_version(provider_id: str, provider_versions: list[dict[str, str]]) -> str:
    for item in provider_versions:
        if item.get("provider_id") == provider_id:
            return item.get("version", "unknown")
    return "unknown"
