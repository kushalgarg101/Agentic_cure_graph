"""SQLite-backed persistence for analysis jobs and results."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class SQLiteStore:
    """Durable storage for analyses and dataset metadata."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def initialize(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            current_version = self.schema_version(conn)
            if current_version < 1:
                self._migrate_v1(conn)
                self._set_schema_version(conn, 1)
                current_version = 1
            if current_version < 2:
                self._migrate_v2(conn)
                self._set_schema_version(conn, 2)

    def schema_version(self, conn: sqlite3.Connection | None = None) -> int:
        if conn is not None:
            return int(conn.execute("PRAGMA user_version").fetchone()[0])
        with self._connect() as local_conn:
            return int(local_conn.execute("PRAGMA user_version").fetchone()[0])

    def mark_incomplete_as_failed(self, detail: str) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE analyses
                SET status = 'failed',
                    detail = ?,
                    error_detail = COALESCE(error_detail, ?),
                    updated_at = ?,
                    completed_at = COALESCE(completed_at, ?)
                WHERE status IN ('queued', 'running')
                """,
                (detail, detail, now, now),
            )

    def record_dataset(self, provider_id: str, version: str, description: str, kind: str = "unknown") -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO datasets (provider_id, version, description, kind, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(provider_id) DO UPDATE SET
                    version = excluded.version,
                    description = excluded.description,
                    kind = excluded.kind,
                    updated_at = excluded.updated_at
                """,
                (provider_id, version, description, kind, now),
            )

    def list_datasets(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT provider_id, version, description, kind, updated_at FROM datasets ORDER BY provider_id"
            ).fetchall()
        return [
            {
                "provider_id": row["provider_id"],
                "version": row["version"],
                "description": row["description"],
                "kind": row["kind"],
                "updated_at": row["updated_at"],
            }
            for row in rows
        ]

    def create_analysis(
        self,
        analysis_id: str,
        payload: dict[str, Any],
        *,
        input_format: str,
        evidence_mode: str,
        with_ai: bool,
        detail: str = "Queued",
    ) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO analyses (
                    id, status, detail, input_format, evidence_mode, with_ai,
                    request_json, created_at, updated_at
                ) VALUES (?, 'queued', ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    analysis_id,
                    detail,
                    input_format,
                    evidence_mode,
                    1 if with_ai else 0,
                    json.dumps(payload),
                    now,
                    now,
                ),
            )

    def set_running(self, analysis_id: str, detail: str = "Running analysis") -> None:
        self._set_status(analysis_id, "running", detail)

    def set_failed(self, analysis_id: str, detail: str) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE analyses
                SET status = 'failed',
                    detail = ?,
                    error_detail = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (detail, detail, now, now, analysis_id),
            )

    def set_completed(
        self,
        analysis_id: str,
        *,
        graph: dict[str, Any],
        stats: dict[str, Any],
        warnings: list[str],
        policy: dict[str, Any],
        dataset_versions: list[dict[str, Any]],
        source_provenance: list[dict[str, Any]],
        input_quality: str,
    ) -> None:
        now = utc_now()
        meta = graph.get("meta", {})
        provider_ids = sorted({item.get("provider_id", "unknown") for item in dataset_versions})
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE analyses
                SET status = 'completed',
                    detail = 'Complete',
                    graph_json = ?,
                    stats_json = ?,
                    warnings_json = ?,
                    policy_json = ?,
                    dataset_versions_json = ?,
                    source_provenance_json = ?,
                    provider_ids_json = ?,
                    input_quality = ?,
                    patient_summary = ?,
                    hypothesis_count = ?,
                    node_count = ?,
                    link_count = ?,
                    updated_at = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    json.dumps(graph),
                    json.dumps(stats),
                    json.dumps(warnings),
                    json.dumps(policy),
                    json.dumps(dataset_versions),
                    json.dumps(source_provenance),
                    json.dumps(provider_ids),
                    input_quality,
                    str(meta.get("patient_case_summary", "")),
                    int(meta.get("hypothesis_count", 0)),
                    len(graph.get("nodes", [])),
                    len(graph.get("links", [])),
                    now,
                    now,
                    analysis_id,
                ),
            )

    def get_analysis(self, analysis_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM analyses WHERE id = ?", (analysis_id,)).fetchone()
        return self._row_to_analysis(row) if row else None

    def list_analyses(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM analyses ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._row_to_analysis(row) for row in rows]

    def count_analyses(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM analyses").fetchone()
        return int(row["count"]) if row else 0

    def count_incomplete(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS count FROM analyses WHERE status IN ('queued', 'running')"
            ).fetchone()
        return int(row["count"]) if row else 0

    def _set_status(self, analysis_id: str, status: str, detail: str) -> None:
        now = utc_now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE analyses SET status = ?, detail = ?, updated_at = ? WHERE id = ?",
                (status, detail, now, analysis_id),
            )

    def _row_to_analysis(self, row: sqlite3.Row) -> dict[str, Any]:
        graph = _loads(row["graph_json"], {})
        stats = _loads(row["stats_json"], {})
        warnings = _loads(row["warnings_json"], [])
        policy = _loads(row["policy_json"], {})
        dataset_versions = _loads(row["dataset_versions_json"], [])
        source_provenance = _loads(row["source_provenance_json"], [])
        request_payload = _loads(row["request_json"], {})
        provider_ids = _loads(row["provider_ids_json"], [])
        return {
            "id": row["id"],
            "status": row["status"],
            "detail": row["detail"],
            "input_format": row["input_format"],
            "evidence_mode": row["evidence_mode"],
            "with_ai": bool(row["with_ai"]),
            "request": request_payload,
            "graph": graph,
            "stats": stats,
            "warnings": warnings,
            "policy": policy,
            "dataset_versions": dataset_versions,
            "source_provenance": source_provenance,
            "provider_ids": provider_ids,
            "input_quality": row["input_quality"] or "unknown",
            "patient_summary": row["patient_summary"] or "",
            "hypothesis_count": int(row["hypothesis_count"] or 0),
            "node_count": int(row["node_count"] or 0),
            "link_count": int(row["link_count"] or 0),
            "error_detail": row["error_detail"] or "",
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "completed_at": row["completed_at"],
        }

    def _migrate_v1(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS analyses (
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

            CREATE TABLE IF NOT EXISTS datasets (
                provider_id TEXT PRIMARY KEY,
                version TEXT NOT NULL,
                description TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_analyses_status ON analyses(status);
            CREATE INDEX IF NOT EXISTS idx_analyses_created_at ON analyses(created_at DESC);
            """
        )

    def _migrate_v2(self, conn: sqlite3.Connection) -> None:
        analysis_columns = self._column_names(conn, "analyses")
        if "input_quality" not in analysis_columns:
            conn.execute("ALTER TABLE analyses ADD COLUMN input_quality TEXT NOT NULL DEFAULT 'unknown'")
        if "provider_ids_json" not in analysis_columns:
            conn.execute("ALTER TABLE analyses ADD COLUMN provider_ids_json TEXT NOT NULL DEFAULT '[]'")

        dataset_columns = self._column_names(conn, "datasets")
        if "kind" not in dataset_columns:
            conn.execute("ALTER TABLE datasets ADD COLUMN kind TEXT NOT NULL DEFAULT 'unknown'")

    def _column_names(self, conn: sqlite3.Connection, table_name: str) -> set[str]:
        rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _set_schema_version(self, conn: sqlite3.Connection, version: int) -> None:
        conn.execute(f"PRAGMA user_version = {int(version)}")

    def _connect(self) -> sqlite3.Connection:
        with self._lock:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            conn.row_factory = sqlite3.Row
            return conn


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default
