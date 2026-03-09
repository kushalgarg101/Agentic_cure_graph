"""MCP tool definitions for the Agentic Cure Graph.

Each tool function takes structured input and returns a dict that
can be serialized as JSON. These tools are called by AI agents
through the MCP protocol.
"""

from __future__ import annotations

import logging
from typing import Any

from agents.patient_insight_agent import extract_patient_insight
from agents.hypothesis_agent import generate_hypotheses
from agents.evidence_agent import validate_hypotheses
from github_viz.analysis.stats import compute_stats, search_nodes, find_shortest_path

logger = logging.getLogger(__name__)


def query_cure_graph(patient_data: dict[str, Any]) -> dict[str, Any]:
    """Full pipeline: patient data → Cure Graph → hypotheses → evidence.

    This is the primary MCP tool. It runs the complete agentic pipeline:
    1. Patient Insight Agent extracts entities.
    2. Hypothesis Agent builds the graph and ranks hypotheses.
    3. Evidence Agent validates each hypothesis.

    Returns a structured report suitable for AI consumption.
    """
    logger.info("MCP tool: query_cure_graph")

    # Stage 1: Patient Insight
    insight = extract_patient_insight(patient_data, source="mcp")
    patient_case = insight.to_patient_case()

    # Stage 2: Hypothesis Generation
    hypothesis_result = generate_hypotheses(
        patient_case,
        report_text=insight.report_text,
        evidence_mode="hybrid",
    )

    # Stage 3: Evidence Validation
    hypothesis_dicts = [
        {**h.to_dict(), "meta": {
            "supporting_paper_ids": h.supporting_paper_ids,
            "biomarker_overlap": h.biomarker_overlap,
        }}
        for h in hypothesis_result.hypotheses
    ]
    validation = validate_hypotheses(
        hypothesis_result.graph,
        hypothesis_dicts,
        session_id=hypothesis_result.session_id,
    )

    return {
        "session_id": hypothesis_result.session_id,
        "patient_summary": hypothesis_result.patient_summary,
        "hypothesis_count": len(hypothesis_result.hypotheses),
        "analysis_time_s": hypothesis_result.analysis_time_s,
        "warnings": hypothesis_result.warnings,
        "dataset_versions": hypothesis_result.dataset_versions,
        "policy": hypothesis_result.policy,
        "hypotheses": [h.to_dict() for h in hypothesis_result.hypotheses],
        "evidence_validation": validation.to_dict(),
    }


def find_disease_hypotheses(disease: str) -> dict[str, Any]:
    """Find hypotheses for a specific disease.

    Creates a minimal patient case with just the disease and runs
    the pipeline. Useful for exploratory queries.
    """
    logger.info("MCP tool: find_disease_hypotheses(%s)", disease)

    patient_case = {
        "patient_id": "mcp-query",
        "diagnoses": [disease],
    }

    result = generate_hypotheses(patient_case, evidence_mode="hybrid")

    return {
        "disease": disease,
        "hypotheses": [h.to_dict() for h in result.hypotheses],
    }


def search_research_papers(query: str, session_graph: dict[str, Any] | None = None) -> dict[str, Any]:
    """Search for research papers in a graph.

    If no graph is provided, runs a minimal pipeline to build one.
    """
    logger.info("MCP tool: search_research_papers(%s)", query)

    if session_graph is None:
        # Build a graph from the query as a diagnosis
        result = generate_hypotheses(
            {"patient_id": "search-query", "diagnoses": [query]},
            evidence_mode="hybrid",
        )
        session_graph = result.graph

    results = search_nodes(session_graph, query)
    papers = [r for r in results if r.get("type") == "research_paper"]

    return {
        "query": query,
        "paper_count": len(papers),
        "papers": [
            {
                "id": p.get("id", ""),
                "title": p.get("label", ""),
                "journal": p.get("meta", {}).get("journal", ""),
                "year": p.get("meta", {}).get("year", ""),
            }
            for p in papers[:20]
        ],
    }


def get_graph_stats(graph: dict[str, Any]) -> dict[str, Any]:
    """Compute and return graph-level analytics."""
    logger.info("MCP tool: get_graph_stats")
    return compute_stats(graph)


def find_path_between_entities(
    graph: dict[str, Any],
    source: str,
    target: str,
) -> dict[str, Any]:
    """Find shortest path between two entities in the Cure Graph."""
    logger.info("MCP tool: find_path_between_entities(%s → %s)", source, target)
    path = find_shortest_path(graph, source, target)
    return {
        "source": source,
        "target": target,
        "path": path,
        "hops": len(path) - 1 if path else None,
        "found": path is not None,
    }


# ── Tool registry for MCP protocol ──────────────────────────────────

MCP_TOOLS = [
    {
        "name": "query_cure_graph",
        "description": "Analyze a patient case through the full Agentic Cure Graph pipeline. "
                       "Extracts entities, generates hypotheses, and validates evidence.",
        "parameters": {
            "type": "object",
            "properties": {
                "patient_data": {
                    "type": "object",
                    "description": "Patient case data with fields: patient_id, age_range, sex, "
                                   "diagnoses, symptoms, biomarkers, medications, report_text",
                },
            },
            "required": ["patient_data"],
        },
        "handler": query_cure_graph,
    },
    {
        "name": "find_disease_hypotheses",
        "description": "Find treatment hypotheses for a specific disease using the Cure Graph.",
        "parameters": {
            "type": "object",
            "properties": {
                "disease": {
                    "type": "string",
                    "description": "The disease name to find hypotheses for",
                },
            },
            "required": ["disease"],
        },
        "handler": find_disease_hypotheses,
    },
    {
        "name": "search_research_papers",
        "description": "Search for research papers related to a biomedical query.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query for research papers",
                },
            },
            "required": ["query"],
        },
        "handler": search_research_papers,
    },
]
