"""A2A Protocol implementation for Agentic Cure Graph.

This module provides A2A (Agent-to-Agent) protocol support, allowing
 Cure Graph agents to be discovered and called by other A2A-compatible agents.

A2A Protocol Spec: https://google-a2a.github.io/A2A/specification/
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Literal
from enum import Enum

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task status values in A2A protocol."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


@dataclass
class AgentSkill:
    """An agent skill that can be invoked."""

    id: str
    name: str
    description: str
    input_modes: list[str] = field(default_factory=lambda: ["text", "data"])
    output_modes: list[str] = field(default_factory=lambda: ["text", "data"])


@dataclass
class AgentCard:
    """Agent Card for A2A discovery (JSON metadata)."""

    name: str
    description: str
    url: str
    version: str
    skills: list[AgentSkill]
    capabilities: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "version": self.version,
            "skills": [
                {
                    "id": s.id,
                    "name": s.name,
                    "description": s.description,
                    "inputModes": s.input_modes,
                    "outputModes": s.output_modes,
                }
                for s in self.skills
            ],
            "capabilities": self.capabilities,
        }


@dataclass
class MessagePart:
    """A message part in A2A protocol."""

    type: Literal["text", "data", "resource"]
    content: str | dict[str, Any]
    mime_type: str | None = None


@dataclass
class A2AMessage:
    """A2A message structure."""

    message_id: str
    role: Literal["user", "agent"]
    parts: list[MessagePart]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """A2A task for agent interaction."""

    id: str
    status: TaskStatus
    message: A2AMessage | None = None
    result: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class A2AAgent:
    """Base class for A2A-compatible agents."""

    def __init__(self, agent_id: str, name: str, description: str):
        self.agent_id = agent_id
        self.name = name
        self.description = description
        self._skills: list[AgentSkill] = []

    def add_skill(self, skill: AgentSkill):
        """Add a skill to this agent."""
        self._skills.append(skill)

    def get_agent_card(self, base_url: str) -> AgentCard:
        """Get the A2A Agent Card for this agent."""
        return AgentCard(
            name=self.name,
            description=self.description,
            url=f"{base_url}/agents/{self.agent_id}",
            version="1.0.0",
            skills=self._skills,
            capabilities={
                "streaming": True,
                "pushNotifications": False,
            },
        )

    async def process_task(self, task: Task) -> Task:
        """Process an A2A task. Override in subclasses."""
        raise NotImplementedError


def create_patient_insight_agent_card(
    base_url: str = "http://localhost:8000",
) -> AgentCard:
    """Create Agent Card for Patient Insight Agent."""
    return AgentCard(
        name="Patient Insight Agent",
        description="Extracts structured biomedical entities from patient records (FHIR or structured). "
        "Identifies diagnoses, symptoms, biomarkers, and medications.",
        url=f"{base_url}/a2a/agents/patient-insight",
        version="1.0.0",
        skills=[
            AgentSkill(
                id="extract-patient-insight",
                name="Extract Patient Insight",
                description="Extract structured entities from patient data including diagnoses, symptoms, biomarkers, and medications",
            ),
        ],
        capabilities={
            "streaming": True,
            "pushNotifications": False,
        },
    )


def create_hypothesis_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Create Agent Card for Hypothesis Agent."""
    return AgentCard(
        name="Hypothesis Agent",
        description="Generates and ranks treatment hypotheses from patient data using the Cure Graph. "
        "Provides evidence-backed research hypotheses.",
        url=f"{base_url}/a2a/agents/hypothesis",
        version="1.0.0",
        skills=[
            AgentSkill(
                id="generate-hypotheses",
                name="Generate Hypotheses",
                description="Generate ranked treatment hypotheses from patient case data",
            ),
            AgentSkill(
                id="query-disease-hypotheses",
                name="Query Disease Hypotheses",
                description="Find hypotheses for a specific disease",
            ),
        ],
        capabilities={
            "streaming": True,
            "pushNotifications": False,
        },
    )


def create_evidence_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Create Agent Card for Evidence Agent."""
    return AgentCard(
        name="Evidence Agent",
        description="Validates hypotheses against research evidence. "
        "Computes evidence scores and retrieves supporting papers.",
        url=f"{base_url}/a2a/agents/evidence",
        version="1.0.0",
        skills=[
            AgentSkill(
                id="validate-hypotheses",
                name="Validate Hypotheses",
                description="Validate hypotheses against research papers and compute evidence scores",
            ),
        ],
        capabilities={
            "streaming": True,
            "pushNotifications": False,
        },
    )


def create_cure_graph_agent_card(base_url: str = "http://localhost:8000") -> AgentCard:
    """Create Agent Card for the combined Cure Graph Agent."""
    return AgentCard(
        name="Cure Graph Agent",
        description="Full biomedical discovery agent. Takes patient data and returns "
        "ranked hypotheses with evidence validation.",
        url=f"{base_url}/a2a/agents/cure-graph",
        version="1.0.0",
        skills=[
            AgentSkill(
                id="query-cure-graph",
                name="Query Cure Graph",
                description="Full pipeline: patient data → Cure Graph → hypotheses → evidence validation",
            ),
            AgentSkill(
                id="search-papers",
                name="Search Research Papers",
                description="Search biomedical literature related to a query",
            ),
            AgentSkill(
                id="find-paths",
                name="Find Entity Paths",
                description="Find paths between entities in the knowledge graph",
            ),
        ],
        capabilities={
            "streaming": True,
            "pushNotifications": False,
        },
    )


def get_all_agent_cards(base_url: str = "http://localhost:8000") -> list[AgentCard]:
    """Get all Agent Cards for Cure Graph agents."""
    return [
        create_patient_insight_agent_card(base_url),
        create_hypothesis_agent_card(base_url),
        create_evidence_agent_card(base_url),
        create_cure_graph_agent_card(base_url),
    ]
