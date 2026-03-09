"""Command-line interface for Agentic Cure Graph."""

from __future__ import annotations

import json
import logging
import uuid

import typer
import uvicorn

from github_viz.config import get_settings
from github_viz.logging_config import configure_logging
from github_viz.persistence import SQLiteStore
from github_viz.providers import build_provider_registry, dataset_versions
from github_viz.server import create_app
from github_viz.services import run_analysis

logger = logging.getLogger(__name__)
app = typer.Typer(add_completion=False, no_args_is_help=True)


def _parse_csv(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


@app.command()
def analyze(
    patient_id: str = typer.Option("patient-record", "--patient-id", help="Patient record identifier"),
    age_range: str = typer.Option("60-69", "--age-range", help="Age band"),
    sex: str = typer.Option("unknown", "--sex", help="female|male|other|unknown"),
    diagnoses: str = typer.Option("Parkinson's disease", "--diagnoses", help="Comma-separated diagnoses"),
    symptoms: str = typer.Option("Tremor,Rigidity", "--symptoms", help="Comma-separated symptoms"),
    biomarkers: str = typer.Option("Elevated inflammation", "--biomarkers", help="Comma-separated biomarkers"),
    medications: str = typer.Option("Metformin", "--medications", help="Comma-separated medications"),
    report_text: str = typer.Option("", "--report-text", help="Optional narrative report text"),
    evidence_mode: str = typer.Option("hybrid", "--evidence-mode", help="offline|hybrid"),
    with_ai: bool = typer.Option(False, "--with-ai", help="Enable AI summaries"),
    ai_api_key: str | None = typer.Option(None, "--ai-api-key", help="LLM API key override"),
    ai_base_url: str | None = typer.Option(None, "--ai-base-url", help="LLM base URL override"),
    ai_model: str | None = typer.Option(None, "--ai-model", help="LLM model override"),
) -> None:
    """Run Cure Graph analysis and print graph JSON."""
    settings = get_settings()
    configure_logging(settings.log_level)
    providers = build_provider_registry(settings)

    result = run_analysis(
        analysis_id=str(uuid.uuid4()),
        patient_case={
            "patient_id": patient_id,
            "age_range": age_range,
            "sex": sex,
            "diagnoses": _parse_csv(diagnoses),
            "symptoms": _parse_csv(symptoms),
            "biomarkers": _parse_csv(biomarkers),
            "medications": _parse_csv(medications),
        },
        report_text=report_text,
        evidence_mode=evidence_mode,
        with_ai=with_ai,
        ai_options={
            "api_key": ai_api_key,
            "base_url": ai_base_url,
            "model": ai_model,
        } if with_ai else None,
        providers=providers,
    )
    typer.echo(json.dumps(result["graph"], indent=2))


@app.command()
def serve(port: int = typer.Option(get_settings().port, "--port", help="API port")) -> None:
    """Start the FastAPI server."""
    configure_logging(get_settings().log_level)
    uvicorn.run(create_app(), host=get_settings().host, port=port, log_level="info")


@app.command("init-db")
def init_db() -> None:
    """Initialize the SQLite database and register bundled datasets."""
    settings = get_settings()
    configure_logging(settings.log_level)
    store = SQLiteStore(settings.db_path)
    store.initialize()
    for dataset in dataset_versions(build_provider_registry(settings), evidence_mode="hybrid"):
        store.record_dataset(
            dataset["provider_id"],
            dataset["version"],
            dataset["description"],
            dataset.get("kind", "unknown"),
        )
    typer.echo(f"Initialized database at {settings.db_path}")


@app.command("datasets")
def show_datasets() -> None:
    """Print registered dataset metadata."""
    settings = get_settings()
    configure_logging(settings.log_level)
    store = SQLiteStore(settings.db_path)
    store.initialize()
    for dataset in dataset_versions(build_provider_registry(settings), evidence_mode="hybrid"):
        store.record_dataset(
            dataset["provider_id"],
            dataset["version"],
            dataset["description"],
            dataset.get("kind", "unknown"),
        )
    typer.echo(json.dumps({"items": store.list_datasets()}, indent=2))


if __name__ == "__main__":
    app()
