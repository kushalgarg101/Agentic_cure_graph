"""Tests for the FastAPI Cure Graph endpoints."""

import asyncio

import httpx
import pytest

from github_viz.server import create_app


@pytest.fixture
def analyze_payload():
    return {
        "patient_case": {
            "patient_id": "demo-001",
            "age_range": "60-69",
            "sex": "female",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Tremor"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        },
        "report_text": "Narrative mentions activated microglia and elevated CRP in a Parkinson disease patient.",
        "evidence_mode": "hybrid",
        "with_ai": False,
    }


def request(app, method, path, **kwargs):
    async def _run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(_run())


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
def session_id(app, analyze_payload):
    response = request(app, "POST", "/analyze/local", json=analyze_payload)
    assert response.status_code == 200
    return response.json()["id"]


def test_health(app):
    response = request(app, "GET", "/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_get_graph(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}")
    assert response.status_code == 200
    graph = response.json()
    assert graph["meta"]["hypothesis_count"] >= 1
    assert any(node["type"] == "patient" for node in graph["nodes"])


def test_get_stats(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}/stats")
    assert response.status_code == 200
    stats = response.json()
    assert stats["patient_profile"]["diagnosis_count"] == 1
    assert stats["top_hypotheses"][0]["label"] == "Metformin for Parkinson's disease"


def test_search(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}/search", params={"q": "metformin"})
    assert response.status_code == 200
    assert response.json()["results"]


def test_shortest_path(app, session_id):
    response = request(
        app,
        "GET",
        f"/graph/{session_id}/path",
        params={"from": "patient:demo-001", "to": "paper:metformin-neuroinflammation-2023"},
    )
    assert response.status_code == 200
    assert response.json()["hops"] >= 1


def test_hypotheses_endpoint(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}/hypotheses")
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["type"] == "hypothesis"
