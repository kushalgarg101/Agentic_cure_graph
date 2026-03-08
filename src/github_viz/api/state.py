"""In-memory runtime state for analysis sessions.

This module intentionally keeps state local to the process. It provides a
thread-safe LRU graph store and per-session status tracking.
"""

from __future__ import annotations

import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Literal


StatusType = Literal["pending", "running", "done", "error"]


@dataclass
class AnalysisStatus:
    """Represents execution state for a single session."""

    status: StatusType
    detail: str


class SessionStore:
    """Thread-safe LRU store for graph sessions and their status."""

    def __init__(self, max_sessions: int = 50) -> None:
        self._max_sessions = max_sessions
        self._graphs: OrderedDict[str, dict] = OrderedDict()
        self._status: dict[str, AnalysisStatus] = {}
        self._lock = threading.RLock()

    def set_status(self, session_id: str, status: StatusType, detail: str) -> None:
        """Set status for a session, creating it when needed."""
        with self._lock:
            self._status[session_id] = AnalysisStatus(status=status, detail=detail)

    def get_status(self, session_id: str) -> AnalysisStatus | None:
        """Return status for a session if it exists."""
        with self._lock:
            return self._status.get(session_id)

    def set_graph(self, session_id: str, graph: dict) -> None:
        """Store graph and enforce LRU capacity."""
        with self._lock:
            if session_id in self._graphs:
                self._graphs.move_to_end(session_id)
            self._graphs[session_id] = graph
            while len(self._graphs) > self._max_sessions:
                oldest_id, _ = self._graphs.popitem(last=False)
                self._status.pop(oldest_id, None)

    def get_graph(self, session_id: str) -> dict | None:
        """Return graph and mark it recently used."""
        with self._lock:
            graph = self._graphs.get(session_id)
            if graph is not None:
                self._graphs.move_to_end(session_id)
            return graph

    def has_graph(self, session_id: str) -> bool:
        """Check whether a graph exists for the given session."""
        with self._lock:
            return session_id in self._graphs

    def list_sessions(self) -> list[dict]:
        """Return metadata for active graph sessions."""
        with self._lock:
            sessions: list[dict] = []
            for sid, graph in self._graphs.items():
                meta = graph.get("meta", {})
                status = self._status.get(sid, AnalysisStatus("done", "Complete"))
                sessions.append(
                    {
                        "id": sid,
                        "subject": meta.get("patient_case_summary", ""),
                        "generated_at": meta.get("generated_at", ""),
                        "nodes": len(graph.get("nodes", [])),
                        "links": len(graph.get("links", [])),
                        "status": status.status,
                    }
                )
            return sessions

    def session_count(self) -> int:
        """Return the number of cached graph sessions."""
        with self._lock:
            return len(self._graphs)
