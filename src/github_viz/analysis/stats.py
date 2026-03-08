"""Graph analytics utilities for the Cure Graph dashboard and search endpoints."""

from __future__ import annotations

from collections import defaultdict, deque
from statistics import mean
from typing import Any


def compute_stats(graph: dict) -> dict[str, Any]:
    """Compute graph-level analytics used by the API."""
    nodes = graph.get("nodes", [])
    links = graph.get("links", [])

    in_degree: dict[str, int] = defaultdict(int)
    out_degree: dict[str, int] = defaultdict(int)
    for link in links:
        source = link.get("source")
        target = link.get("target")
        if not source or not target:
            continue
        out_degree[source] += 1
        in_degree[target] += 1

    node_ids = {node.get("id") for node in nodes if node.get("id")}
    orphan_ids = sorted([node_id for node_id in node_ids if in_degree[node_id] == 0 and out_degree[node_id] == 0])
    degree = {node_id: in_degree[node_id] + out_degree[node_id] for node_id in node_ids}
    most_connected = sorted(degree.items(), key=lambda item: item[1], reverse=True)[:10]

    type_counts: dict[str, int] = defaultdict(int)
    for node in nodes:
        type_counts[str(node.get("type") or "unknown")] += 1

    hypotheses = sorted(
        [node for node in nodes if node.get("type") == "hypothesis"],
        key=lambda item: float(item.get("score", 0.0)),
        reverse=True,
    )
    papers = [node for node in nodes if node.get("type") == "research_paper"]
    patient_node = next((node for node in nodes if node.get("type") == "patient"), {})

    evidence_support_counts = [int(node.get("evidence_count", 0)) for node in hypotheses]
    hypothesis_rankings = [
        {
            "id": item.get("id"),
            "label": item.get("label"),
            "score": round(float(item.get("score", 0.0)), 3),
            "evidence_count": int(item.get("evidence_count", 0)),
            "rationale": item.get("meta", {}).get("rationale", ""),
            "supporting_paper_ids": item.get("meta", {}).get("supporting_paper_ids", []),
        }
        for item in hypotheses[:10]
    ]

    top_entities = []
    for node_id, value in most_connected:
        node = next((entry for entry in nodes if entry.get("id") == node_id), {"id": node_id})
        top_entities.append(
            {
                "id": node_id,
                "label": node.get("label") or node_id,
                "type": node.get("type"),
                "degree": value,
            }
        )

    return {
        "total_nodes": len(nodes),
        "total_links": len(links),
        "orphan_nodes": len(orphan_ids),
        "orphan_ids": orphan_ids[:20],
        "max_degree": max(degree.values(), default=0),
        "most_connected": top_entities,
        "entity_counts": dict(type_counts),
        "top_hypotheses": hypothesis_rankings,
        "patient_profile": {
            "id": patient_node.get("id", ""),
            "label": patient_node.get("label", ""),
            "summary": patient_node.get("summary", ""),
            "diagnosis_count": len(patient_node.get("meta", {}).get("diagnoses", [])),
            "symptom_count": len(patient_node.get("meta", {}).get("symptoms", [])),
            "biomarker_count": len(patient_node.get("meta", {}).get("biomarkers", [])),
            "medication_count": len(patient_node.get("meta", {}).get("medications", [])),
        },
        "evidence_coverage": {
            "paper_nodes": len(papers),
            "hypothesis_nodes": len(hypotheses),
            "hypotheses_with_evidence": sum(1 for count in evidence_support_counts if count > 0),
            "avg_supporting_papers": round(mean(evidence_support_counts), 2) if evidence_support_counts else 0.0,
        },
    }


def find_shortest_path(graph: dict, source: str, target: str) -> list[str] | None:
    """Run BFS shortest path search on an undirected graph projection."""
    node_ids = {node.get("id") for node in graph.get("nodes", []) if node.get("id")}
    if source not in node_ids or target not in node_ids:
        return None
    if source == target:
        return [source]

    adjacency: dict[str, list[str]] = defaultdict(list)
    for link in graph.get("links", []):
        src = link.get("source")
        dst = link.get("target")
        if not src or not dst:
            continue
        adjacency[src].append(dst)
        adjacency[dst].append(src)

    queue: deque[list[str]] = deque([[source]])
    visited: set[str] = {source}

    while queue:
        path = queue.popleft()
        current = path[-1]
        for neighbor in adjacency[current]:
            if neighbor in visited:
                continue
            candidate = [*path, neighbor]
            if neighbor == target:
                return candidate
            visited.add(neighbor)
            queue.append(candidate)
    return None


def search_nodes(graph: dict, query: str) -> list[dict]:
    """Search over node labels, ids, summaries, and metadata."""
    needle = query.strip().lower()
    if not needle:
        return []

    results: list[dict] = []
    for node in graph.get("nodes", []):
        fields = [
            str(node.get("id", "")),
            str(node.get("label", "")),
            str(node.get("summary", "")),
            str(node.get("type", "")),
            str(node.get("group", "")),
            str(node.get("meta", {})),
        ]
        haystack = " ".join(fields).lower()
        score = 0
        if needle == str(node.get("label", "")).lower():
            score += 8
        if needle in str(node.get("label", "")).lower():
            score += 5
        if needle in str(node.get("id", "")).lower():
            score += 4
        if needle in haystack:
            score += 2
        if score > 0:
            results.append({**node, "_search_score": score})

    results.sort(key=lambda item: (item["_search_score"], item.get("score", 0.0)), reverse=True)
    return results[:50]
