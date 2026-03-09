"""Evidence Agent — validates hypotheses against research papers and graph structure.

This agent takes the generated hypotheses plus the full graph and computes
evidence scores, retrieves supporting papers, and produces a validation
report for each hypothesis.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from github_viz.analysis.stats import compute_stats

logger = logging.getLogger(__name__)


@dataclass
class EvidenceReport:
    """Validation report for a single hypothesis."""

    hypothesis_id: str
    label: str
    original_score: float
    evidence_score: float
    supporting_papers: list[dict[str, Any]] = field(default_factory=list)
    graph_paths: list[list[str]] = field(default_factory=list)
    biomarker_overlap: list[str] = field(default_factory=list)
    validation_status: str = "validated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "label": self.label,
            "original_score": round(self.original_score, 3),
            "evidence_score": round(self.evidence_score, 3),
            "supporting_papers": self.supporting_papers,
            "graph_path_count": len(self.graph_paths),
            "biomarker_overlap": self.biomarker_overlap,
            "validation_status": self.validation_status,
        }


@dataclass
class ValidationResult:
    """Output of the Evidence Agent."""

    session_id: str
    evidence_reports: list[EvidenceReport]
    graph_stats: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_hypotheses_validated": len(self.evidence_reports),
            "validated": sum(1 for r in self.evidence_reports if r.validation_status == "validated"),
            "weak": sum(1 for r in self.evidence_reports if r.validation_status == "weak"),
            "evidence_reports": [r.to_dict() for r in self.evidence_reports],
            "graph_stats": {
                "total_nodes": self.graph_stats.get("total_nodes", 0),
                "total_links": self.graph_stats.get("total_links", 0),
                "paper_nodes": self.graph_stats.get("evidence_coverage", {}).get("paper_nodes", 0),
            },
        }


def validate_hypotheses(
    graph: dict[str, Any],
    hypotheses: list[dict[str, Any]],
    *,
    session_id: str = "",
) -> ValidationResult:
    """Validate a set of hypotheses against the graph's evidence network.

    For each hypothesis the agent:
    1. Finds all supporting research papers connected in the graph.
    2. Computes a weighted evidence score from paper count and biomarker overlap.
    3. Traces graph paths from patient → hypothesis → drug → disease.
    4. Labels the hypothesis as ``validated`` or ``weak``.
    """
    logger.info("Evidence Agent: validating %d hypotheses", len(hypotheses))

    stats = compute_stats(graph)
    nodes = graph.get("nodes", [])
    links = graph.get("links", [])

    # Build adjacency for quick lookups
    adjacency: dict[str, list[dict[str, str]]] = {}
    for link in links:
        src, tgt = link.get("source", ""), link.get("target", "")
        adjacency.setdefault(src, []).append({"target": tgt, "kind": link.get("kind", "")})
        adjacency.setdefault(tgt, []).append({"target": src, "kind": link.get("kind", "")})

    papers_by_id: dict[str, dict] = {
        n["id"]: n for n in nodes if n.get("type") == "research_paper"
    }

    reports: list[EvidenceReport] = []

    for hyp in hypotheses:
        hyp_id = hyp.get("id", hyp.get("hypothesis_id", ""))
        label = hyp.get("label", "")
        original_score = float(hyp.get("score", 0.0))
        meta = hyp.get("meta", {})

        # Find connected papers
        paper_ids = meta.get("supporting_paper_ids", [])
        supporting_papers = []
        for pid in paper_ids:
            paper = papers_by_id.get(pid, {})
            if paper:
                supporting_papers.append({
                    "id": pid,
                    "title": paper.get("label", ""),
                    "journal": paper.get("meta", {}).get("journal", ""),
                    "year": paper.get("meta", {}).get("year", ""),
                })

        # Biomarker overlap
        biomarker_overlap = meta.get("biomarker_overlap", [])

        # Compute evidence score
        paper_weight = min(0.4, len(supporting_papers) * 0.1)
        biomarker_weight = min(0.3, len(biomarker_overlap) * 0.15)
        evidence_score = min(1.0, original_score * 0.5 + paper_weight + biomarker_weight + 0.1)

        # Trace paths from hypothesis
        graph_paths: list[list[str]] = []
        for neighbor in adjacency.get(hyp_id, []):
            path = [hyp_id, neighbor["target"]]
            for second_hop in adjacency.get(neighbor["target"], []):
                if second_hop["target"] != hyp_id:
                    graph_paths.append([*path, second_hop["target"]])
                    break

        validation_status = "validated" if evidence_score >= 0.4 and len(supporting_papers) > 0 else "weak"

        reports.append(EvidenceReport(
            hypothesis_id=hyp_id,
            label=label,
            original_score=original_score,
            evidence_score=evidence_score,
            supporting_papers=supporting_papers,
            graph_paths=graph_paths,
            biomarker_overlap=biomarker_overlap,
            validation_status=validation_status,
        ))

    reports.sort(key=lambda r: r.evidence_score, reverse=True)

    logger.info(
        "Evidence Agent: %d validated, %d weak",
        sum(1 for r in reports if r.validation_status == "validated"),
        sum(1 for r in reports if r.validation_status == "weak"),
    )

    return ValidationResult(
        session_id=session_id,
        evidence_reports=reports,
        graph_stats=stats,
    )
