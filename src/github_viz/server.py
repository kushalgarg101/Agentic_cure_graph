"""FastAPI application factory and HTTP endpoints for Agentic Cure Graph."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from github_viz.analysis.llm import enrich_case_summary
from github_viz.analysis.stats import find_shortest_path, search_nodes
from github_viz.api.schemas import (
    AnalysisCreatedResponse,
    AnalysisStatusResponse,
    AnalyzeLocalRequest,
    AnalyzeRequest,
    FhirNormalizeRequest,
)

from github_viz.config import Settings, get_settings
from github_viz.ingestion.fhir import parse_fhir_record
from github_viz.logging_config import configure_logging
from github_viz.persistence import SCHEMA_VERSION, SQLiteStore
from github_viz.providers import build_provider_registry, dataset_versions
from github_viz.services import collect_evidence, collect_hypotheses, run_analysis

logger = logging.getLogger(__name__)


class EnrichRequest(BaseModel):
    hypothesis_id: str
    patient_summary: str
    hypothesis_label: str
    hypothesis_mechanism: str = ""


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    store = SQLiteStore(settings.db_path)
    store.initialize()
    store.mark_incomplete_as_failed("Analysis interrupted by service restart.")

    providers = build_provider_registry(settings)
    for dataset in dataset_versions(providers, evidence_mode="hybrid"):
        store.record_dataset(
            dataset["provider_id"],
            dataset["version"],
            dataset["description"],
            dataset.get("kind", "unknown"),
        )

    executor = ThreadPoolExecutor(max_workers=settings.analysis_workers)
    started_at = time.time()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            app.state.executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title=settings.app_name, version=settings.app_version, lifespan=lifespan)
    app.state.settings = settings
    app.state.store = store
    app.state.providers = providers
    app.state.executor = executor
    app.state.started_at = started_at

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allow_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_timing_middleware(request: Request, call_next):
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        response.headers["x-request-id"] = request_id
        response.headers["x-process-time-ms"] = f"{elapsed_ms:.2f}"
        logger.info(
            "request_id=%s method=%s path=%s status=%d duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response

    def _analysis_worker(analysis_id: str, req: AnalyzeRequest) -> None:
        app.state.store.set_running(analysis_id, "Generating Cure Graph")
        try:
            result = run_analysis(
                analysis_id=analysis_id,
                patient_case=req.patient_case.model_dump(),
                report_text=req.report_text,
                evidence_mode=req.evidence_mode,
                with_ai=req.with_ai,
                ai_options=req.ai.model_dump(exclude_none=True) if req.ai else None,
                providers=app.state.providers,
            )
            app.state.store.set_completed(
                analysis_id,
                graph=result["graph"],
                stats=result["stats"],
                warnings=result["warnings"],
                policy=result["policy"],
                dataset_versions=result["dataset_versions"],
                source_provenance=result["source_provenance"],
                input_quality=result["input_quality"],
            )
        except Exception as exc:
            logger.exception("Analysis failed for analysis_id=%s", analysis_id)
            app.state.store.set_failed(analysis_id, str(exc))

    # Timeout-wrapped version to prevent infinite hangs
    ANALYSIS_TIMEOUT_SECONDS = 120

    def _safe_analysis_worker(analysis_id: str, req: AnalyzeRequest) -> None:
        """Run analysis with a timeout guard."""
        inner_executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = inner_executor.submit(_analysis_worker, analysis_id, req)
            future.result(timeout=ANALYSIS_TIMEOUT_SECONDS)
        except FuturesTimeoutError:
            logger.error("Analysis timed out after %ds for analysis_id=%s", ANALYSIS_TIMEOUT_SECONDS, analysis_id)
            app.state.store.set_failed(analysis_id, f"Analysis timed out after {ANALYSIS_TIMEOUT_SECONDS}s. Try 'offline' evidence mode.")
        except Exception as exc:
            logger.exception("Unexpected error in safe worker for analysis_id=%s", analysis_id)
            if not app.state.store.get_analysis(analysis_id).get("completed_at"):
                app.state.store.set_failed(analysis_id, str(exc))
        finally:
            inner_executor.shutdown(wait=False, cancel_futures=True)

    def _create_analysis(req: AnalyzeRequest) -> str:
        analysis_id = str(uuid.uuid4())
        app.state.store.create_analysis(
            analysis_id,
            req.model_dump(),
            input_format=req.input_format,
            evidence_mode=req.evidence_mode,
            with_ai=req.with_ai,
        )
        return analysis_id

    def _run_sync_analysis(req: AnalyzeRequest) -> dict:
        analysis_id = _create_analysis(req)
        app.state.store.set_running(analysis_id, "Generating Cure Graph")
        try:
            result = run_analysis(
                analysis_id=analysis_id,
                patient_case=req.patient_case.model_dump(),
                report_text=req.report_text,
                evidence_mode=req.evidence_mode,
                with_ai=req.with_ai,
                ai_options=req.ai.model_dump(exclude_none=True) if req.ai else None,
                providers=app.state.providers,
            )
            app.state.store.set_completed(
                analysis_id,
                graph=result["graph"],
                stats=result["stats"],
                warnings=result["warnings"],
                policy=result["policy"],
                dataset_versions=result["dataset_versions"],
                source_provenance=result["source_provenance"],
                input_quality=result["input_quality"],
            )
            analysis = app.state.store.get_analysis(analysis_id)
            if analysis is None:
                raise HTTPException(status_code=500, detail="analysis result was not persisted")
            return analysis
        except Exception as exc:
            logger.exception("Local analysis failed for analysis_id=%s", analysis_id)
            app.state.store.set_failed(analysis_id, str(exc))
            raise HTTPException(status_code=500, detail=str(exc))

    def _get_analysis_or_404(analysis_id: str) -> dict:
        analysis = app.state.store.get_analysis(analysis_id)
        if analysis is None:
            raise HTTPException(status_code=404, detail="analysis not found")
        return analysis

    def _analysis_status_body(analysis: dict, compatibility: bool = False) -> dict:
        status = analysis["status"]
        if compatibility:
            if status == "completed":
                status = "done"
            elif status == "failed":
                status = "error"

        return AnalysisStatusResponse(
            id=analysis["id"],
            status=status,
            detail=analysis["detail"],
            created_at=analysis["created_at"],
            updated_at=analysis["updated_at"],
            completed_at=analysis["completed_at"],
            node_count=analysis["node_count"],
            link_count=analysis["link_count"],
            hypothesis_count=analysis["hypothesis_count"],
            warnings=analysis["warnings"],
        ).model_dump()

    def _graph_or_202(analysis: dict) -> dict:
        if analysis["graph"]:
            return analysis["graph"]
        if analysis["status"] in {"queued", "running"}:
            raise HTTPException(status_code=202, detail="Analysis in progress")
        if analysis["status"] == "failed":
            raise HTTPException(status_code=500, detail=analysis["error_detail"] or analysis["detail"])
        raise HTTPException(status_code=404, detail="graph not found")

    @app.get("/health")
    def health() -> dict:
        uptime_s = round(time.time() - app.state.started_at, 2)
        return {
            "status": "ok",
            "uptime_s": uptime_s,
            "analyses": app.state.store.count_analyses(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    @app.get("/ready")
    def ready() -> dict:
        active_datasets = dataset_versions(app.state.providers, evidence_mode="hybrid")
        if not active_datasets:
            raise HTTPException(status_code=503, detail="No evidence providers are configured")
        return {
            "status": "ready",
            "db_path": str(settings.db_path),
            "schema_version": app.state.store.schema_version(),
            "expected_schema_version": SCHEMA_VERSION,
            "providers": active_datasets,
            "incomplete_analyses": app.state.store.count_incomplete(),
        }

    @app.get("/datasets")
    def list_datasets() -> dict:
        return {"items": app.state.store.list_datasets()}

    @app.post("/fhir/normalize")
    def normalize_fhir(req: FhirNormalizeRequest) -> dict:
        normalized = parse_fhir_record(req.record)
        normalized["input_format"] = "fhir"
        return normalized

    @app.post("/analyses", response_model=AnalysisCreatedResponse)
    def create_analysis(req: AnalyzeRequest):
        analysis_id = _create_analysis(req)
        app.state.executor.submit(_safe_analysis_worker, analysis_id, req)
        return AnalysisCreatedResponse(id=analysis_id, status="queued", detail="Queued")

    @app.get("/analyses")
    def list_analyses(limit: int = Query(50, ge=1, le=200)):
        items = []
        for analysis in app.state.store.list_analyses(limit=limit):
            items.append(
                {
                    **_analysis_status_body(analysis),
                    "input_format": analysis["input_format"],
                    "evidence_mode": analysis["evidence_mode"],
                    "patient_summary": analysis["patient_summary"],
                    "input_quality": analysis["input_quality"],
                    "provider_ids": analysis["provider_ids"],
                }
            )
        return {"items": items}

    @app.get("/analyses/{analysis_id}", response_model=AnalysisStatusResponse)
    def get_analysis_status(analysis_id: str):
        analysis = _get_analysis_or_404(analysis_id)
        return _analysis_status_body(analysis)

    @app.get("/analyses/{analysis_id}/graph")
    def get_analysis_graph(analysis_id: str):
        analysis = _get_analysis_or_404(analysis_id)
        return _graph_or_202(analysis)

    @app.get("/analyses/{analysis_id}/stats")
    def get_analysis_stats(analysis_id: str):
        analysis = _get_analysis_or_404(analysis_id)
        if not analysis["stats"]:
            _graph_or_202(analysis)
        return analysis["stats"]

    @app.get("/analyses/{analysis_id}/hypotheses")
    def get_analysis_hypotheses(analysis_id: str):
        analysis = _get_analysis_or_404(analysis_id)
        graph = _graph_or_202(analysis)
        return {"items": collect_hypotheses(graph)}

    @app.get("/analyses/{analysis_id}/evidence")
    def get_analysis_evidence(analysis_id: str):
        analysis = _get_analysis_or_404(analysis_id)
        graph = _graph_or_202(analysis)
        return {"items": collect_evidence(graph)}

    @app.get("/analyses/{analysis_id}/search")
    def search_analysis_graph(analysis_id: str, q: str = Query(..., min_length=1)):
        analysis = _get_analysis_or_404(analysis_id)
        graph = _graph_or_202(analysis)
        return {"query": q, "results": search_nodes(graph, q)}

    @app.get("/analyses/{analysis_id}/path")
    def path_in_analysis_graph(
        analysis_id: str,
        source: str = Query(..., alias="from"),
        target: str = Query(..., alias="to"),
    ):
        analysis = _get_analysis_or_404(analysis_id)
        graph = _graph_or_202(analysis)
        path = find_shortest_path(graph, source, target)
        if path is None:
            raise HTTPException(status_code=404, detail="No path found between the given nodes")
        return {"source": source, "target": target, "path": path, "hops": len(path) - 1}

    @app.post("/analyze")
    def analyze(req: AnalyzeRequest):
        analysis_id = _create_analysis(req)
        app.state.executor.submit(_safe_analysis_worker, analysis_id, req)
        return {"id": analysis_id, "status": "queued"}

    @app.post("/analyze/local")
    def analyze_local(req: AnalyzeLocalRequest):
        analysis = _run_sync_analysis(req)
        status = analysis["status"]
        if status == "completed":
            status = "done"
        return {"id": analysis["id"], "status": status, "graph": analysis["graph"]}

    @app.get("/analyze/status/{session_id}")
    def analysis_status(session_id: str):
        analysis = _get_analysis_or_404(session_id)
        body = _analysis_status_body(analysis, compatibility=True)
        body["nodes"] = analysis["node_count"]
        body["links"] = analysis["link_count"]
        return body

    @app.get("/sessions")
    def list_sessions():
        items = []
        for analysis in app.state.store.list_analyses(limit=100):
            status = analysis["status"]
            if status == "completed":
                status = "done"
            elif status == "failed":
                status = "error"
            items.append(
                {
                    "id": analysis["id"],
                    "subject": analysis["patient_summary"],
                    "generated_at": analysis["completed_at"] or analysis["created_at"],
                    "nodes": analysis["node_count"],
                    "links": analysis["link_count"],
                    "status": status,
                    "input_quality": analysis["input_quality"],
                    "provider_ids": analysis["provider_ids"],
                }
            )
        return {"sessions": items}

    @app.get("/graph/{session_id}")
    def get_graph(session_id: str):
        analysis = _get_analysis_or_404(session_id)
        return _graph_or_202(analysis)

    @app.get("/graph/{session_id}/stats")
    def get_stats(session_id: str):
        analysis = _get_analysis_or_404(session_id)
        if not analysis["stats"]:
            _graph_or_202(analysis)
        return analysis["stats"]

    @app.get("/graph/{session_id}/search")
    def search(session_id: str, q: str = Query(..., min_length=1)):
        analysis = _get_analysis_or_404(session_id)
        graph = _graph_or_202(analysis)
        return {"query": q, "results": search_nodes(graph, q)}

    @app.get("/graph/{session_id}/path")
    def shortest_path(
        session_id: str,
        source: str = Query(..., alias="from"),
        target: str = Query(..., alias="to"),
    ):
        analysis = _get_analysis_or_404(session_id)
        graph = _graph_or_202(analysis)
        path = find_shortest_path(graph, source, target)
        if path is None:
            raise HTTPException(status_code=404, detail="No path found between the given nodes")
        return {"source": source, "target": target, "path": path, "hops": len(path) - 1}

    @app.get("/graph/{session_id}/hypotheses")
    def list_hypotheses(session_id: str):
        analysis = _get_analysis_or_404(session_id)
        graph = _graph_or_202(analysis)
        return {"items": collect_hypotheses(graph)}

    @app.post("/enrich")
    def enrich_hypothesis(req: EnrichRequest):
        hypothesis_dict = {
            "id": req.hypothesis_id,
            "label": req.hypothesis_label,
            "summary": req.hypothesis_mechanism,
        }
        try:
            result = enrich_case_summary(req.patient_summary, [hypothesis_dict])
        except Exception as exc:
            logger.warning("Enrichment call failed: %s", exc)
            return {"enrichment": "AI enrichment unavailable. Please check API keys."}

        if result.get("status") == "completed":
            return {"enrichment": result.get("top_hypothesis_summary", "")}
        return {"enrichment": result.get("reason", "AI enrichment unavailable. Please check API keys.")}

    @app.get("/")
    def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "ok",
            "intended_use": "Clinician-facing research assistant backend",
            "not_for_diagnostic_use": True,
            "endpoints": [
                "/health",
                "/ready",
                "/datasets",
                "/fhir/normalize",
                "/analyses",
                "/analyses/{analysis_id}",
                "/analyses/{analysis_id}/graph",
                "/analyses/{analysis_id}/stats",
                "/analyses/{analysis_id}/hypotheses",
                "/analyses/{analysis_id}/evidence",
            ],
            "compatibility_endpoints": [
                "/analyze",
                "/analyze/local",
                "/analyze/status/{session_id}",
                "/graph/{session_id}",
            ],
        }

    return app


app = create_app()
