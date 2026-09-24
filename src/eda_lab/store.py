import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
          job_id TEXT PRIMARY KEY, design_id TEXT NOT NULL, ip_family TEXT NOT NULL,
          flow_name TEXT NOT NULL, status TEXT NOT NULL, parse_status TEXT NOT NULL,
          check_status TEXT NOT NULL, completeness TEXT NOT NULL DEFAULT 'unknown',
          provenance TEXT NOT NULL DEFAULT '{}', artifact_path TEXT, error TEXT
        );
        CREATE TABLE IF NOT EXISTS metrics (
          job_id TEXT PRIMARY KEY REFERENCES runs(job_id), payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attempts (
          job_id TEXT NOT NULL REFERENCES runs(job_id), attempt_no INTEGER NOT NULL,
          status TEXT NOT NULL, error_type TEXT, error TEXT, artifact_path TEXT,
          PRIMARY KEY(job_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS metric_rows (
          id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES runs(job_id),
          metric_name TEXT NOT NULL, stage TEXT NOT NULL, corner TEXT NOT NULL,
          value REAL NOT NULL, unit TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metric_rows_stage_corner ON metric_rows(stage, corner, metric_name);
        """)
        self.connection.commit()

    def create_run(self, job_id: str, design_id: str, ip_family: str, flow_name: str) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR IGNORE INTO runs(job_id, design_id, ip_family, flow_name, status, parse_status, check_status, completeness, provenance) "
                "VALUES (?, ?, ?, ?, 'QUEUED', 'NOT_STARTED', 'UNKNOWN', 'unknown', '{}')",
                (job_id, design_id, ip_family, flow_name),
            )
            self.connection.commit()

    def update_run(self, job_id: str, **fields: Any) -> None:
        allowed = {"status", "parse_status", "check_status", "completeness", "provenance", "artifact_path", "error"}
        fields = {key: value for key, value in fields.items() if key in allowed}
        if not fields:
            return
        if "provenance" in fields:
            fields["provenance"] = json.dumps(fields["provenance"] or {}, sort_keys=True)
        assignments = ", ".join(f"{key} = ?" for key in fields)
        with self._lock:
            self.connection.execute(f"UPDATE runs SET {assignments} WHERE job_id = ?", (*fields.values(), job_id))
            self.connection.commit()

    def record_attempt(self, job_id: str, attempt_no: int, status: str, *, error_type: str | None = None,
                       error: str | None = None, artifact_path: str | None = None) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT OR REPLACE INTO attempts(job_id, attempt_no, status, error_type, error, artifact_path) VALUES (?, ?, ?, ?, ?, ?)",
                (job_id, attempt_no, status, error_type, error, artifact_path),
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
