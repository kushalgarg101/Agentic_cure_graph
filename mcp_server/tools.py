"""MCP tool definitions for Agentic Cure Graph using official MCP SDK.

These tools are called by AI agents through the MCP protocol.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from agents.patient_insight_agent import extract_patient_insight
from agents.hypothesis_agent import generate_hypotheses
from agents.evidence_agent import validate_hypotheses
from github_viz.analysis.stats import compute_stats, search_nodes, find_shortest_path
from github_viz.config import get_settings

logger = logging.getLogger(__name__)


def create_mcp_server() -> Server:
    """Create and configure the MCP server with tools."""

    server = Server(
        name="agentic-cure-graph",
        version="1.0.0",
    )

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of available tools."""
        return [
            Tool(
                name="query_cure_graph",
                description="Analyze a patient case through the full Agentic Cure Graph pipeline. "
                "Extracts entities, generates hypotheses, and validates evidence.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "patient_data": {
                            "type": "object",
                            "description": "Patient case data with fields: patient_id, age_range, sex, "
                            "diagnoses, symptoms, biomarkers, medications, report_text",
                            "properties": {
                                "patient_id": {
                                    "type": "string",
                                    "description": "Patient identifier",
                                },
                                "age_range": {
                                    "type": "string",
                                    "description": "Age band (e.g., 60-69)",
                                },
                                "sex": {
                                    "type": "string",
                                    "enum": ["male", "female", "other", "unknown"],
                                },
                                "diagnoses": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of diagnoses",
                                },
                                "symptoms": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of symptoms",
                                },
                                "biomarkers": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of biomarkers",
                                },
                                "medications": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of medications",
                                },
                                "report_text": {
                                    "type": "string",
                                    "description": "Optional narrative report",
                                },
                            },
                        },
                    },
                    "required": ["patient_data"],
                },
            ),
            Tool(
                name="find_disease_hypotheses",
                description="Find treatment hypotheses for a specific disease using the Cure Graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "disease": {
                            "type": "string",
                            "description": "The disease name to find hypotheses for (e.g., 'Parkinson's disease')",
                        },
                    },
                    "required": ["disease"],
                },
            ),
            Tool(
                name="search_research_papers",
                description="Search for research papers related to a biomedical query.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search query for research papers",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results (default 20)",
                            "default": 20,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="get_graph_stats",
                description="Compute and return graph-level analytics.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph": {
                            "type": "object",
                            "description": "The Cure Graph JSON object",
                        },
                    },
                    "required": ["graph"],
                },
            ),
            Tool(
                name="find_path_between_entities",
                description="Find shortest path between two entities in the Cure Graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "graph": {
                            "type": "object",
                            "description": "The Cure Graph JSON object",
                        },
                        "source": {
                            "type": "string",
                            "description": "Source entity name",
                        },
                        "target": {
                            "type": "string",
                            "description": "Target entity name",
                        },
                    },
                    "required": ["graph", "source", "target"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        """Handle tool calls from MCP clients."""
        if arguments is None:
            arguments = {}

        try:
            if name == "query_cure_graph":
                result = await _query_cure_graph(arguments.get("patient_data", {}))
            elif name == "find_disease_hypotheses":
                result = await _find_disease_hypotheses(arguments.get("disease", ""))
            elif name == "search_research_papers":
                result = await _search_research_papers(
                    arguments.get("query", ""), arguments.get("max_results", 20)
                )
            elif name == "get_graph_stats":
                result = await _get_graph_stats(arguments.get("graph", {}))
            elif name == "find_path_between_entities":
                result = await _find_path_between_entities(
                    arguments.get("graph", {}),
                    arguments.get("source", ""),
                    arguments.get("target", ""),
                )
            else:
                result = {"error": f"Unknown tool: {name}"}

            return [TextContent(type="text", text=_json_dumps(result))]

        except Exception as e:
            logger.exception(f"MCP tool call failed: {name}")
            return [TextContent(type="text", text=_json_dumps({"error": str(e)}))]

    return server


async def _query_cure_graph(patient_data: dict[str, Any]) -> dict[str, Any]:
    """Full pipeline: patient data → Cure Graph → hypotheses → evidence."""
    logger.info("MCP tool: query_cure_graph")

    insight = extract_patient_insight(patient_data, source="mcp")
    patient_case = insight.to_patient_case()

    hypothesis_result = generate_hypotheses(
        patient_case,
        report_text=insight.report_text,
        evidence_mode="hybrid",
    )

    hypothesis_dicts = [
        {
            **h.to_dict(),
            "meta": {
                "supporting_paper_ids": h.supporting_paper_ids,
                "biomarker_overlap": h.biomarker_overlap,
            },
        }
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


async def _find_disease_hypotheses(disease: str) -> dict[str, Any]:
    """Find hypotheses for a specific disease."""
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


async def _search_research_papers(query: str, max_results: int = 20) -> dict[str, Any]:
    """Search for research papers in a graph."""
    logger.info("MCP tool: search_research_papers(%s)", query)

    result = generate_hypotheses(
        {"patient_id": "search-query", "diagnoses": [query]},
        evidence_mode="hybrid",
    )

    results = search_nodes(result.graph, query)
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
            for p in papers[:max_results]
        ],
    }


async def _get_graph_stats(graph: dict[str, Any]) -> dict[str, Any]:
    """Compute and return graph-level analytics."""
    logger.info("MCP tool: get_graph_stats")
    return compute_stats(graph)


async def _find_path_between_entities(
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


def _json_dumps(obj: Any) -> str:
    """Simple JSON serialize."""
    import json

    return json.dumps(obj, default=str)


async def run_mcp_server():
    """Run the MCP server over stdio."""
    server = create_mcp_server()
    async with stdio_server() as streams:
        await server.run(
            streams[0],
            streams[1],
            server.create_initialization_options(),
        )
