import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: str | Path = ":memory:", now=None):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._now = now or time.time
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
          job_id TEXT PRIMARY KEY, design_id TEXT NOT NULL, ip_family TEXT NOT NULL,
          flow_name TEXT NOT NULL, status TEXT NOT NULL, parse_status TEXT NOT NULL,
          check_status TEXT NOT NULL, completeness TEXT NOT NULL DEFAULT 'unknown',
          provenance TEXT NOT NULL DEFAULT '{}', artifact_path TEXT, error TEXT,
          updated_at REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS metrics (
          job_id TEXT PRIMARY KEY REFERENCES runs(job_id), payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attempts (
          job_id TEXT NOT NULL REFERENCES runs(job_id), attempt_no INTEGER NOT NULL,
          status TEXT NOT NULL, error_type TEXT, error TEXT, artifact_path TEXT,
          retry_class TEXT, started_at REAL NOT NULL DEFAULT 0, updated_at REAL NOT NULL DEFAULT 0,
          PRIMARY KEY(job_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS metric_rows (
          id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES runs(job_id),
          metric_name TEXT NOT NULL, stage TEXT NOT NULL, corner TEXT NOT NULL,
          value REAL NOT NULL, unit TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metric_rows_stage_corner ON metric_rows(stage, corner, metric_name);
        """)
        self._add_column_if_missing("runs", "updated_at", "REAL NOT NULL DEFAULT 0")
        self._add_column_if_missing("attempts", "retry_class", "TEXT")
        self._add_column_if_missing("attempts", "started_at", "REAL NOT NULL DEFAULT 0")
        self._add_column_if_missing("attempts", "updated_at", "REAL NOT NULL DEFAULT 0")
        self.connection.commit()

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def now(self) -> float:
        return self._now()

    def create_run(self, job_id: str, design_id: str, ip_family: str, flow_name: str) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR IGNORE INTO runs(job_id, design_id, ip_family, flow_name, status, parse_status, check_status, completeness, provenance, updated_at) "
                "VALUES (?, ?, ?, ?, 'QUEUED', 'NOT_STARTED', 'UNKNOWN', 'unknown', '{}', ?)",
                (job_id, design_id, ip_family, flow_name, self._now()),
            )
            self.connection.commit()

    def update_run(self, job_id: str, **fields: Any) -> None:
        allowed = {"status", "parse_status", "check_status", "completeness", "provenance", "artifact_path", "error"}
        fields = {key: value for key, value in fields.items() if key in allowed}
        if not fields:
            return
        if "provenance" in fields:
            fields["provenance"] = json.dumps(fields["provenance"] or {}, sort_keys=True)
        fields["updated_at"] = self._now()
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._lock:
            self.connection.execute(f"UPDATE runs SET {assignments} WHERE job_id = ?", (*fields.values(), job_id))
            self.connection.commit()

    def record_attempt(self, job_id: str, attempt_no: int, status: str, *, error_type: str | None = None,
                       error: str | None = None, artifact_path: str | None = None,
                       retry_class: str | None = None) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO attempts(job_id, attempt_no, status, error_type, error, artifact_path, retry_class, started_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(job_id, attempt_no) DO UPDATE SET "
                "status=excluded.status, error_type=excluded.error_type, error=excluded.error, "
                "artifact_path=COALESCE(excluded.artifact_path, attempts.artifact_path), "
                "retry_class=excluded.retry_class, updated_at=excluded.updated_at",
                (job_id, attempt_no, status, error_type, error, artifact_path, retry_class, self._now(), self._now()),
            )
            self.connection.commit()

    def save_metrics(self, job_id: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self.connection.execute("INSERT OR REPLACE INTO metrics(job_id, payload) VALUES (?, ?)", (job_id, json.dumps(payload, sort_keys=True)))
            self.connection.commit()

    def save_metric_rows(self, rows: list[tuple[str, str, str, str, float, str]]) -> None:
        with self._lock:
            self.connection.executemany(
                "INSERT INTO metric_rows(job_id, metric_name, stage, corner, value, unit) VALUES (?, ?, ?, ?, ?, ?)",
                rows,
            )
            self.connection.commit()

    def query_metric_summary(self, stage: str, corner: str, metric_name: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute(
                "SELECT COUNT(*) AS count, MIN(value) AS min_value, MAX(value) AS max_value, AVG(value) AS avg_value "
                "FROM metric_rows WHERE stage = ? AND corner = ? AND metric_name = ?",
                (stage, corner, metric_name),
            ).fetchone()
            return dict(row) if row and row["count"] else None

    def get_run(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self.connection.execute("SELECT * FROM runs WHERE job_id = ?", (job_id,)).fetchone()
            if row is None:
                return None
            result = dict(row)
            result["provenance"] = json.loads(result["provenance"] or "{}")
            metric = self.connection.execute("SELECT payload FROM metrics WHERE job_id = ?", (job_id,)).fetchone()
            result["metrics"] = json.loads(metric["payload"]) if metric else None
            result["attempts"] = [dict(item) for item in self.connection.execute(
                "SELECT * FROM attempts WHERE job_id = ? ORDER BY attempt_no", (job_id,)
            ).fetchall()]
            return result

    def list_stale_running(self, cutoff: float) -> list[dict[str, Any]]:
        with self._lock:
            job_ids = [row["job_id"] for row in self.connection.execute(
                "SELECT job_id FROM runs WHERE status = 'RUNNING' AND updated_at <= ?", (cutoff,)
            ).fetchall()]
        return [run for job_id in job_ids if (run := self.get_run(job_id)) is not None]
