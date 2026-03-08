"""Core graph domain models used across analysis and API layers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

NodeType = Literal[
    "patient",
    "disease",
    "symptom",
    "biomarker",
    "drug",
    "gene",
    "protein",
    "pathway",
    "research_paper",
    "hypothesis",
]


@dataclass
class Node:
    """Represents a Cure Graph node."""

    id: str
    type: NodeType
    label: str
    summary: str = ""
    group: str = ""
    language: str = "bio"
    size: int = 1
    complexity: int = 0
    issues: int = 0
    churn: int = 0
    line_count: int = 0
    contributors: int = 0
    last_modified: str = ""
    content: str = ""
    score: float = 0.0
    evidence_count: int = 0
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize node into plain dict for JSON output."""
        return asdict(self)


@dataclass
class Link:
    """Represents a directional relationship between two biomedical nodes."""

    source: str
    target: str
    kind: str
    weight: int = 1
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Serialize link into plain dict for JSON output."""
        return asdict(self)
