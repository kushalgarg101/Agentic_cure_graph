"""Tests for the FastAPI Cure Graph endpoints."""

import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from github_viz.config import Settings
from github_viz.server import create_app


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


TEST_DB_DIR = Path(__file__).resolve().parents[1] / "var_test"


def build_test_db_path() -> Path:
    TEST_DB_DIR.mkdir(exist_ok=True)
    return TEST_DB_DIR / f"{uuid4().hex}.db"


@pytest.fixture
def app():
    settings = Settings(
        db_path=build_test_db_path(),
        allow_origins=("*",),
    )
    return create_app(settings)


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
    assert datasets.json()["items"][0]["provider_id"] == "curated_seed"
    assert datasets.json()["items"][0]["kind"] == "bundled_seed"


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
        params={"from": "patient:case-001", "to": "paper:metformin-neuroinflammation-2023"},
    )
    assert response.status_code == 200
    assert response.json()["hops"] >= 1


def test_hypotheses_endpoint(app, session_id):
    response = request(app, "GET", f"/graph/{session_id}/hypotheses")
    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    assert body["items"][0]["type"] == "hypothesis"
    assert body["items"][0]["classification"] in {"supported", "exploratory", "insufficient_evidence"}


def test_analyses_resource_and_evidence(app, analyze_payload):
    created = request(app, "POST", "/analyses", json=analyze_payload)
    assert created.status_code == 200
    analysis_id = created.json()["id"]

    for _ in range(20):
        status = request(app, "GET", f"/analyses/{analysis_id}")
        assert status.status_code == 200
        if status.json()["status"] == "completed":
            break
    else:
        pytest.fail("analysis did not complete")

    evidence = request(app, "GET", f"/analyses/{analysis_id}/evidence")
    analyses = request(app, "GET", "/analyses")
    assert evidence.status_code == 200
    assert evidence.json()["items"]
    assert analyses.status_code == 200
    assert any(item["id"] == analysis_id for item in analyses.json()["items"])


def test_completed_analysis_survives_app_restart(analyze_payload):
    settings = Settings(db_path=build_test_db_path(), allow_origins=("*",))
    app_one = create_app(settings)
    created = request(app_one, "POST", "/analyze/local", json=analyze_payload)
    analysis_id = created.json()["id"]

    app_two = create_app(settings)
    response = request(app_two, "GET", f"/analyses/{analysis_id}/graph")
    assert response.status_code == 200
    assert response.json()["meta"]["analysis_id"] == analysis_id
