"""A2A Protocol Server for Agentic Cure Graph.

This module provides an A2A server that exposes Cure Graph agents
for agent-to-agent communication following the A2A protocol spec.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents.a2a import (
    get_all_agent_cards,
    create_cure_graph_agent_card,
    Task,
    TaskStatus,
    MessagePart,
)

logger = logging.getLogger(__name__)


class TaskSubmitRequest(BaseModel):
    """A2A task submission request."""

    id: str | None = None
    message: dict[str, Any]


class A2AServer:
    """A2A Server for Cure Graph agents."""

    def __init__(self):
        self.tasks: dict[str, Task] = {}

    async def handle_submit_task(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle task submission."""
        task_id = request.get("id", str(uuid.uuid4()))
        message_data = request.get("message", {})

        # Extract text from message parts
        text_content = ""
        data_content = {}

        for part in message_data.get("parts", []):
            if part.get("type") == "text":
                text_content += part.get("text", "")
            elif part.get("type") == "data":
                data_content = part.get("data", {})

        logger.info("A2A task submitted: %s - %s", task_id, text_content[:100])

        # Create task
        task = Task(
            id=task_id,
            status=TaskStatus.WORKING,
            message=None,
            result=None,
        )
        self.tasks[task_id] = task

        # Process the task (this would call the actual agents)
        try:
            result = await self._process_task_message(text_content, data_content)
            task.status = TaskStatus.COMPLETED
            task.result = result
        except Exception as e:
            logger.exception("Task processing failed: %s", task_id)
            task.status = TaskStatus.FAILED
            task.result = {"error": str(e)}

        return {
            "id": task_id,
            "status": task.status.value,
            "result": task.result,
        }

    async def _process_task_message(self, text: str, data: dict) -> dict[str, Any]:
        """Process the task message and return result."""
        from agents.patient_insight_agent import extract_patient_insight
        from agents.hypothesis_agent import generate_hypotheses
        from agents.evidence_agent import validate_hypotheses

        # Use text or data as patient data
        patient_data = data if data else {}
        if not patient_data and text:
            # Try to parse as disease name
            patient_data = {
                "patient_id": "a2a-query",
                "diagnoses": [text] if text else [],
            }

        # Run the full pipeline
        insight = extract_patient_insight(patient_data, source="a2a")
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
            "hypotheses": [h.to_dict() for h in hypothesis_result.hypotheses],
            "evidence_validation": validation.to_dict(),
        }

    async def handle_get_task(self, task_id: str) -> dict[str, Any]:
        """Get task status and result."""
        task = self.tasks.get(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")

        return {
            "id": task.id,
            "status": task.status.value,
            "result": task.result,
        }


def create_a2a_app() -> FastAPI:
    """Create FastAPI app with A2A endpoints."""

    a2a_server = A2AServer()

    app = FastAPI(
        title="Agentic Cure Graph - A2A Server",
        version="1.0.0",
        description="A2A (Agent-to-Agent) protocol server for Cure Graph agents",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/")
    def root():
        return {
            "name": "Agentic Cure Graph A2A Server",
            "version": "1.0.0",
            "protocol": "A2A",
        }

    @app.get("/a2a/agentCard")
    def get_agent_card():
        """Get the main Agent Card for Cure Graph."""
        card = create_cure_graph_agent_card()
        return card.to_dict()

    @app.get("/a2a/agentCard.json")
    def get_agent_card_json():
        """Get the main Agent Card (JSON format)."""
        card = create_cure_graph_agent_card()
        return card.to_dict()

    @app.get("/a2a/agents")
    def list_agents():
        """List all available A2A agents."""
        cards = get_all_agent_cards()
        return {"agents": [card.to_dict() for card in cards]}

    @app.post("/a2a/tasks/submit")
    async def submit_task(request: Request):
        """Submit a new A2A task."""
        body = await request.json()
        return await a2a_server.handle_submit_task(body)

    @app.get("/a2a/tasks/{task_id}")
    async def get_task(task_id: str):
        """Get task status and result."""
        return await a2a_server.handle_get_task(task_id)

    @app.get("/health")
    def health():
        return {"status": "ok", "a2a": "available"}

    return app


if __name__ == "__main__":
    import uvicorn

    app = create_a2a_app()
    uvicorn.run(app, host="127.0.0.1", port=8002)
