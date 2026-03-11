"""Tests for the FastAPI Cure Graph endpoints."""

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from github_viz.config import Settings
from github_viz.server import create_app


TEST_DB_DIR = Path(__file__).resolve().parents[1] / "var_test"
TEST_OVERLAY_DIR = Path(__file__).resolve().parents[1] / "var_test"


def build_test_db_path() -> Path:
    TEST_DB_DIR.mkdir(exist_ok=True)
    return TEST_DB_DIR / f"{uuid4().hex}.db"


def build_test_overlay_path() -> Path:
    TEST_OVERLAY_DIR.mkdir(exist_ok=True)
    path = TEST_OVERLAY_DIR / f"server-test-{uuid4().hex}.json"
    payload = {
        "provider_id": "test_provider",
        "version": "2026.03-test",
        "description": "Test data for server tests",
        "entities": {
            "drugs": [{"id": "drug:metformin", "label": "Metformin"}],
            "diseases": [{"id": "disease:parkinson", "label": "Parkinson's disease"}],
        },
        "papers": [
            {
                "id": "paper:test-001",
                "title": "Metformin in Parkinson's",
                "journal": "Test Journal",
                "year": 2024,
                "citation": "Test Journal (2024)",
                "abstract_snippet": "Test abstract",
                "entities": ["Metformin", "Parkinson's disease"],
            }
        ],
        "relationships": {
            "drug_hypotheses": [
                {
                    "drug": "Metformin",
                    "disease": "Parkinson's disease",
                    "mechanism": "Test mechanism",
                    "biomarker_matches": [],
                    "genes": [],
                    "proteins": [],
                    "pathways": [],
                    "papers": ["paper:test-001"],
                }
            ]
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def request(app, method, path, **kwargs):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


@pytest.fixture
def app():
    overlay_path = build_test_overlay_path()
    settings = Settings(
        db_path=build_test_db_path(),
        allow_origins=("*",),
        extra_provider_paths=(str(overlay_path),),
    )
    return create_app(settings)


@pytest.fixture
def analyze_payload():
    return {
        "patient_case": {
            "patient_id": "case-001",
            "age_range": "60-69",
            "sex": "female",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Tremor"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        },
        "report_text": "Test narrative",
        "evidence_mode": "offline",
        "with_ai": False,
    }


@pytest.fixture
def session_id(app, analyze_payload):
    response = request(app, "POST", "/analyze/local", json=analyze_payload)
    assert response.status_code == 200
    return response.json()["id"]


def test_health(app):
    response = request(app, "GET", "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_and_datasets(app):
    ready = request(app, "GET", "/ready")
    datasets = request(app, "GET", "/datasets")

    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["schema_version"] == ready.json()["expected_schema_version"]
    assert datasets.status_code == 200
    items = datasets.json()["items"]
    assert any(item.get("provider_id") == "test_provider" for item in items)


def test_fhir_normalize(app):
    response = request(
        app,
        "POST",
        "/fhir/normalize",
        json={
            "record": {
                "resourceType": "Patient",
                "id": "fhir-001",
                "gender": "female",
                "age_range": "60-69",
                "condition": ["Parkinson's disease"],
                "observations": ["Elevated inflammation"],
                "medications": ["Metformin"],
            }
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["input_format"] == "fhir"
    assert body["patient_case"]["patient_id"] == "fhir-001"


def test_get_graph(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}")
    assert response.status_code == 200
    graph = response.json()
    assert graph["meta"]["hypothesis_count"] >= 1
    assert any(node["type"] == "patient" for node in graph["nodes"])
    assert graph["meta"]["policy"]["not_for_diagnostic_use"] is True


def test_get_stats(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["patient_profile"]["diagnosis_count"] >= 1


def test_search(app, session_id):
    response = request(
        app, "GET", f"/graph/{session_id}/search", params={"q": "metformin"}
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1


def test_shortest_path(app, session_id):
    response = request(
        app,
        "GET",
        f"/graph/{session_id}/path",
        params={"from": "patient:case-001", "to": "disease:parkinson"},
    )
    assert response.status_code == 200


def test_hypotheses_endpoint(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}/hypotheses")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) >= 1


def test_analyses_resource_and_evidence(app):
    payload = {
        "patient_case": {
            "patient_id": "case-002",
            "diagnoses": ["Parkinson's disease"],
        },
        "evidence_mode": "offline",
        "with_ai": False,
    }
    response = request(app, "POST", "/analyses", json=payload)
    assert response.status_code == 200
    analysis_id = response.json()["id"]

    # Wait a bit and check status
    import time

    time.sleep(0.5)

    status_response = request(app, "GET", f"/analyses/{analysis_id}")
    assert status_response.status_code == 200
