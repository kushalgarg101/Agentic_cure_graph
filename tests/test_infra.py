"""Tests for persistence migrations and provider-backed evidence loading."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from uuid import uuid4

from github_viz.config import Settings
from github_viz.persistence import SCHEMA_VERSION, SQLiteStore
from github_viz.providers import build_provider_registry, dataset_versions
from github_viz.services import run_analysis

TEST_VAR_DIR = Path(__file__).resolve().parents[1] / "var_test"


def _path(name: str, suffix: str) -> Path:
    TEST_VAR_DIR.mkdir(exist_ok=True)
    return TEST_VAR_DIR / f"{name}-{uuid4().hex}{suffix}"


def test_sqlite_store_migrates_legacy_schema():
    db_path = _path("legacy-schema", ".db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        PRAGMA user_version = 1;
        CREATE TABLE analyses (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            detail TEXT NOT NULL,
            input_format TEXT NOT NULL,
            evidence_mode TEXT NOT NULL,
            with_ai INTEGER NOT NULL DEFAULT 0,
            request_json TEXT NOT NULL,
            graph_json TEXT,
            stats_json TEXT,
            warnings_json TEXT,
            policy_json TEXT,
            dataset_versions_json TEXT,
            source_provenance_json TEXT,
            patient_summary TEXT,
            hypothesis_count INTEGER NOT NULL DEFAULT 0,
            node_count INTEGER NOT NULL DEFAULT 0,
            link_count INTEGER NOT NULL DEFAULT 0,
            error_detail TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            completed_at TEXT
        );
        CREATE TABLE datasets (
            provider_id TEXT PRIMARY KEY,
            version TEXT NOT NULL,
            description TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()

    store = SQLiteStore(db_path)
    store.initialize()

    assert store.schema_version() == SCHEMA_VERSION

    verify = sqlite3.connect(db_path)
    analysis_columns = {row[1] for row in verify.execute("PRAGMA table_info(analyses)").fetchall()}
    dataset_columns = {row[1] for row in verify.execute("PRAGMA table_info(datasets)").fetchall()}
    verify.close()

    assert "input_quality" in analysis_columns
    assert "provider_ids_json" in analysis_columns
    assert "kind" in dataset_columns


def test_overlay_provider_participates_in_hybrid_analysis():
    overlay_path = _path("overlay-provider", ".json")
    overlay_payload = {
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
    overlay_path.write_text(json.dumps(overlay_payload), encoding="utf-8")

    settings = Settings(extra_provider_paths=(str(overlay_path),))
    providers = build_provider_registry(settings)
    result = run_analysis(
        analysis_id="overlay-test",
        patient_case={
            "patient_id": "overlay-001",
            "age_range": "60-69",
            "sex": "female",
            "diagnoses": ["Parkinson's disease"],
            "symptoms": ["Tremor"],
            "biomarkers": ["Elevated inflammation"],
            "medications": ["Metformin"],
        },
        report_text="",
        evidence_mode="hybrid",
        with_ai=False,
        ai_options=None,
        providers=providers,
    )

    hypothesis_labels = [node["label"] for node in result["graph"]["nodes"] if node["type"] == "hypothesis"]
    provider_ids = {item["provider_id"] for item in dataset_versions(providers, evidence_mode="hybrid")}
    overlay_provenance = [
        item for item in result["source_provenance"] if "overlay_provider" in item.get("providers", [])
    ]

    assert "Pioglitazone for Parkinson's disease" in hypothesis_labels
    assert provider_ids == {"curated_seed", "overlay_provider"}
    assert overlay_provenance
