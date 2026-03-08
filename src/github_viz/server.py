"""FastAPI application factory and HTTP endpoints for Agentic Cure Graph."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from github_viz.analysis.graph import analyze_case
from github_viz.analysis.stats import compute_stats, find_shortest_path, search_nodes
from github_viz.api.schemas import AnalyzeLocalRequest, AnalyzeRequest
from github_viz.api.state import SessionStore
from github_viz.config import Settings, get_settings
from github_viz.logging_config import configure_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title=settings.app_name, version=settings.app_version)
    app.state.settings = settings
    app.state.sessions = SessionStore(max_sessions=settings.max_sessions)
    app.state.executor = ThreadPoolExecutor(max_workers=settings.analysis_workers)
    app.state.started_at = time.time()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
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

    @app.get("/health")
    def health() -> dict:
        uptime_s = round(time.time() - app.state.started_at, 2)
        return {
            "status": "ok",
            "uptime_s": uptime_s,
            "sessions": app.state.sessions.session_count(),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

    def _analysis_worker(session_id: str, req: AnalyzeRequest) -> None:
        app.state.sessions.set_status(session_id, "running", "Generating Cure Graph")
        try:
            graph = analyze_case(
                patient_case=req.patient_case.model_dump(),
                report_text=req.report_text,
                evidence_mode=req.evidence_mode,
                with_ai=req.with_ai,
                ai_options=req.ai.model_dump(exclude_none=True) if req.ai else None,
            )
            graph["meta"]["session_id"] = session_id
            app.state.sessions.set_graph(session_id, graph)
            app.state.sessions.set_status(session_id, "done", "Complete")
        except Exception as exc:
            logger.exception("Analysis failed for session_id=%s", session_id)
            app.state.sessions.set_status(session_id, "error", str(exc))

    def _run_sync_analysis(session_id: str, req: AnalyzeRequest) -> dict:
        graph = analyze_case(
            patient_case=req.patient_case.model_dump(),
            report_text=req.report_text,
            evidence_mode=req.evidence_mode,
            with_ai=req.with_ai,
            ai_options=req.ai.model_dump(exclude_none=True) if req.ai else None,
        )
        graph["meta"]["session_id"] = session_id
        graph["meta"]["stats"] = compute_stats(graph)
        app.state.sessions.set_graph(session_id, graph)
        app.state.sessions.set_status(session_id, "done", "Complete")
        return graph

    @app.post("/analyze")
    def analyze(req: AnalyzeRequest):
        session_id = str(uuid.uuid4())
        app.state.sessions.set_status(session_id, "pending", "Queued")
        app.state.executor.submit(_analysis_worker, session_id, req)
        return {"id": session_id, "status": "pending"}

    @app.post("/analyze/local")
    def analyze_local(req: AnalyzeLocalRequest):
        session_id = str(uuid.uuid4())
        app.state.sessions.set_status(session_id, "running", "Generating Cure Graph")
        try:
            graph = _run_sync_analysis(session_id, req)
        except Exception as exc:
            logger.exception("Local analysis failed")
            app.state.sessions.set_status(session_id, "error", str(exc))
            raise HTTPException(status_code=500, detail=str(exc))
        return {"id": session_id, "status": "done", "graph": graph}

    @app.get("/analyze/status/{session_id}")
    def analysis_status(session_id: str):
        status = app.state.sessions.get_status(session_id)
        if status is None:
            raise HTTPException(status_code=404, detail="session not found")
        body = {"id": session_id, "status": status.status, "detail": status.detail}
        graph = app.state.sessions.get_graph(session_id)
        if status.status == "done" and graph:
            body["nodes"] = len(graph.get("nodes", []))
            body["links"] = len(graph.get("links", []))
        return body

    @app.get("/sessions")
    def list_sessions():
        return {"sessions": app.state.sessions.list_sessions()}

    @app.get("/graph/{session_id}")
    def get_graph(session_id: str):
        graph = app.state.sessions.get_graph(session_id)
        if graph is not None:
            return graph
        status = app.state.sessions.get_status(session_id)
        if status and status.status in {"pending", "running"}:
            raise HTTPException(status_code=202, detail="Analysis in progress")
        raise HTTPException(status_code=404, detail="session not found")

    @app.get("/graph/{session_id}/stats")
    def get_stats(session_id: str):
        graph = app.state.sessions.get_graph(session_id)
        if graph is None:
            raise HTTPException(status_code=404, detail="session not found")
        return compute_stats(graph)

    @app.get("/graph/{session_id}/search")
    def search(session_id: str, q: str = Query(..., min_length=1)):
        graph = app.state.sessions.get_graph(session_id)
        if graph is None:
            raise HTTPException(status_code=404, detail="session not found")
        return {"query": q, "results": search_nodes(graph, q)}

    @app.get("/graph/{session_id}/path")
    def shortest_path(
        session_id: str,
        source: str = Query(..., alias="from"),
        target: str = Query(..., alias="to"),
    ):
        graph = app.state.sessions.get_graph(session_id)
        if graph is None:
            raise HTTPException(status_code=404, detail="session not found")
        path = find_shortest_path(graph, source, target)
        if path is None:
            raise HTTPException(status_code=404, detail="No path found between the given nodes")
        return {"source": source, "target": target, "path": path, "hops": len(path) - 1}

    @app.get("/graph/{session_id}/hypotheses")
    def list_hypotheses(session_id: str):
        graph = app.state.sessions.get_graph(session_id)
        if graph is None:
            raise HTTPException(status_code=404, detail="session not found")
        hypotheses = sorted(
            [node for node in graph.get("nodes", []) if node.get("type") == "hypothesis"],
            key=lambda item: float(item.get("score", 0.0)),
            reverse=True,
        )
        return {"items": hypotheses}

    @app.get("/")
    def root():
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "ok",
            "endpoints": [
                "/health",
                "/analyze",
                "/analyze/local",
                "/analyze/status/{session_id}",
                "/graph/{session_id}",
                "/graph/{session_id}/stats",
                "/graph/{session_id}/search?q=...",
                "/graph/{session_id}/path?from=...&to=...",
                "/graph/{session_id}/hypotheses",
            ],
        }

    return app
