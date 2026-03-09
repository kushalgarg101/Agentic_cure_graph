"""Tests for agent and MCP paths using the hardened backend services."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from agents.hypothesis_agent import generate_hypotheses
from github_viz.config import Settings, get_settings
from github_viz.providers import build_provider_registry
from mcp_server.tools import query_cure_graph

TEST_VAR_DIR = Path(__file__).resolve().parents[1] / "var_test"


def _overlay_path() -> Path:
    TEST_VAR_DIR.mkdir(exist_ok=True)
    path = TEST_VAR_DIR / f"agent-overlay-{uuid4().hex}.json"
    payload = {
        "provider_id": "overlay_provider",
        "version": "2026.03-overlay",
        "description": "Overlay evidence for an additional Parkinson's hypothesis.",
        "entities": {
            "drugs": [
                {
                    "id": "drug:pioglitazone",
                    "label": "Pioglitazone",
                    "aliases": [],
                }
            ]
        },
        "papers": [
            {
                "id": "paper:pioglitazone-pd-2024",
                "title": "Pioglitazone and inflammatory modulation in Parkinsonian models",
                "journal": "Experimental Neurology",
                "year": 2024,
                "citation": "Experimental Neurology (2024)",
                "abstract_snippet": "Pioglitazone showed exploratory anti-inflammatory activity in Parkinsonian models.",
                "entities": ["Pioglitazone", "Parkinson's disease", "AMPK pathway"],
            }
        ],
        "relationships": {
            "drug_hypotheses": [
                {
                    "drug": "Pioglitazone",
                    "disease": "Parkinson's disease",
                    "mechanism": "Pioglitazone may modulate inflammatory burden through AMPK-associated signaling.",
                    "biomarker_matches": ["Elevated inflammation"],
                    "genes": ["PRKAA1"],
                    "proteins": [],
                    "pathways": ["AMPK pathway"],
                    "papers": ["paper:pioglitazone-pd-2024"],
                }
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_hypothesis_agent_uses_provider_aware_service():
    overlay = _overlay_path()
    settings = Settings(extra_provider_paths=(str(overlay),))
    providers = build_provider_registry(settings)

    result = generate_hypotheses(
        {
            "patient_id": "agent-001",
            "age_range": "60-69",
            "sex": "female",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Tremor"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        },
        evidence_mode="hybrid",
        settings=settings,
        providers=providers,
    )

    labels = [item.label for item in result.hypotheses]
    provider_ids = {item["provider_id"] for item in result.dataset_versions}

    assert "Pioglitazone for Parkinson's disease" in labels
    assert "overlay_provider" in provider_ids
    assert result.policy["not_for_diagnostic_use"] is True
    assert result.dataset_versions


def test_mcp_query_inherits_hardened_metadata(monkeypatch):
    overlay = _overlay_path()
    monkeypatch.setenv("CUREGRAPH_EVIDENCE_PROVIDER_PATHS", str(overlay))
    get_settings.cache_clear()

    result = query_cure_graph(
        {
            "patient_id": "mcp-001",
            "age_range": "60-69",
            "sex": "female",
            "diagnoses": ["Parkinson's disease"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        }
    )

    provider_ids = {item["provider_id"] for item in result["dataset_versions"]}

    assert result["policy"]["not_for_diagnostic_use"] is True
    assert "overlay_provider" in provider_ids
    assert any(item["label"] == "Pioglitazone for Parkinson's disease" for item in result["hypotheses"])

    monkeypatch.delenv("CUREGRAPH_EVIDENCE_PROVIDER_PATHS", raising=False)
    get_settings.cache_clear()
