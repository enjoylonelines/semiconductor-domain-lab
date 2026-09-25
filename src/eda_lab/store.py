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
          semantic_status TEXT NOT NULL DEFAULT 'UNKNOWN', provenance_status TEXT NOT NULL DEFAULT 'UNKNOWN',
          trust_status TEXT NOT NULL DEFAULT 'UNKNOWN',
          provenance TEXT NOT NULL DEFAULT '{}', artifact_path TEXT, error TEXT, spec_hash TEXT,
          updated_at REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS metrics (
          job_id TEXT PRIMARY KEY REFERENCES runs(job_id), payload TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS attempts (
          job_id TEXT NOT NULL REFERENCES runs(job_id), attempt_no INTEGER NOT NULL,
          status TEXT NOT NULL, error_type TEXT, error TEXT, artifact_path TEXT,
          retry_class TEXT, started_at REAL NOT NULL DEFAULT 0, updated_at REAL NOT NULL DEFAULT 0,
          lease_owner TEXT, lease_token TEXT, lease_expires_at REAL, heartbeat_at REAL,
          process_pid INTEGER, process_started_at REAL,
          PRIMARY KEY(job_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS metric_rows (
          id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES runs(job_id),
          metric_name TEXT NOT NULL, stage TEXT NOT NULL, corner TEXT NOT NULL,
          value REAL NOT NULL, unit TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_metric_rows_stage_corner ON metric_rows(stage, corner, metric_name);
        CREATE TABLE IF NOT EXISTS revisions (
          revision_id TEXT PRIMARY KEY, design_id TEXT NOT NULL, source_revision TEXT NOT NULL,
          liberty_hash TEXT NOT NULL, sdc_hash TEXT NOT NULL, tool_version TEXT NOT NULL,
          parser_version TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS findings (
          id INTEGER PRIMARY KEY AUTOINCREMENT, revision_id TEXT NOT NULL REFERENCES revisions(revision_id),
          run_id TEXT NOT NULL, startpoint TEXT NOT NULL, endpoint TEXT NOT NULL,
          path_group TEXT NOT NULL, analysis_type TEXT NOT NULL, corner TEXT NOT NULL,
          slack_ns REAL NOT NULL
        );
        """)
        self._add_column_if_missing("runs", "updated_at", "REAL NOT NULL DEFAULT 0")
        self._add_column_if_missing("runs", "semantic_status", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
        self._add_column_if_missing("runs", "provenance_status", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
        self._add_column_if_missing("runs", "trust_status", "TEXT NOT NULL DEFAULT 'UNKNOWN'")
        self._add_column_if_missing("runs", "spec_hash", "TEXT")
        self._add_column_if_missing("attempts", "retry_class", "TEXT")
        self._add_column_if_missing("attempts", "started_at", "REAL NOT NULL DEFAULT 0")
        self._add_column_if_missing("attempts", "updated_at", "REAL NOT NULL DEFAULT 0")
        self._add_column_if_missing("attempts", "lease_owner", "TEXT")
        self._add_column_if_missing("attempts", "lease_token", "TEXT")
        self._add_column_if_missing("attempts", "lease_expires_at", "REAL")
        self._add_column_if_missing("attempts", "heartbeat_at", "REAL")
        self._add_column_if_missing("attempts", "process_pid", "INTEGER")
        self._add_column_if_missing("attempts", "process_started_at", "REAL")
        self.connection.commit()

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def now(self) -> float:
        return self._now()

    def create_run(self, job_id: str, design_id: str, ip_family: str, flow_name: str, spec_hash: str | None = None) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO runs(job_id, design_id, ip_family, flow_name, status, parse_status, check_status, completeness, semantic_status, provenance_status, trust_status, provenance, spec_hash, updated_at) "
                "VALUES (?, ?, ?, ?, 'QUEUED', 'NOT_STARTED', 'UNKNOWN', 'unknown', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', '{}', ?, ?)",
                (job_id, design_id, ip_family, flow_name, spec_hash, self._now()),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def update_run(self, job_id: str, **fields: Any) -> None:
        allowed = {"status", "parse_status", "check_status", "completeness", "semantic_status", "provenance_status", "trust_status", "provenance", "artifact_path", "error"}
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

    def acquire_attempt_lease(self, job_id: str, attempt_no: int, owner: str, token: str, ttl_seconds: float) -> bool:
        now = self._now()
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET lease_owner = ?, lease_token = ?, heartbeat_at = ?, lease_expires_at = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' "
                "AND (lease_expires_at IS NULL OR lease_expires_at < ?)",
                (owner, token, now, now + ttl_seconds, now, job_id, attempt_no, now),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def heartbeat_attempt(self, job_id: str, attempt_no: int, token: str, ttl_seconds: float) -> bool:
        now = self._now()
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND lease_token = ? AND lease_expires_at >= ?",
                (now, now + ttl_seconds, now, job_id, attempt_no, token, now),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def record_attempt_process(self, job_id: str, attempt_no: int, token: str, pid: int, started_at: float) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET process_pid = ?, process_started_at = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND lease_token = ?",
                (pid, started_at, self._now(), job_id, attempt_no, token),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def transition_attempt(self, job_id: str, attempt_no: int, token: str, status: str, *, error_type: str | None = None,
                           error: str | None = None, artifact_path: str | None = None, retry_class: str | None = None) -> bool:
        """Fence terminal state changes to the lease token that owns this Attempt."""
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET status = ?, error_type = ?, error = ?, artifact_path = COALESCE(?, artifact_path), "
                "retry_class = ?, updated_at = ? WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND lease_token = ?",
                (status, error_type, error, artifact_path, retry_class, self._now(), job_id, attempt_no, token),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def list_expired_leased_attempts(self, now: float | None = None) -> list[tuple[str, int]]:
        cutoff = self._now() if now is None else now
        with self._lock:
            return [tuple(row) for row in self.connection.execute(
                "SELECT job_id, attempt_no FROM attempts WHERE status = 'RUNNING' AND lease_token IS NOT NULL "
                "AND lease_expires_at < ? ORDER BY job_id, attempt_no", (cutoff,)
            ).fetchall()]

    def create_revision(self, revision_id: str, design_id: str, source_revision: str, liberty_hash: str,
                        sdc_hash: str, tool_version: str, parser_version: str) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO revisions VALUES (?, ?, ?, ?, ?, ?, ?)",
                (revision_id, design_id, source_revision, liberty_hash, sdc_hash, tool_version, parser_version),
            )
            self.connection.commit()

    def save_findings(self, revision_id: str, findings: list[tuple[str, str, str, str, str, str, float]]) -> None:
        with self._lock:
            self.connection.executemany(
                "INSERT INTO findings(revision_id, run_id, startpoint, endpoint, path_group, analysis_type, corner, slack_ns) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(revision_id, *finding) for finding in findings],
            )
            self.connection.commit()

    def has_finding_query_index(self) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'index' AND name = 'idx_findings_revision_identity'"
        ).fetchone()
        return row is not None

    def create_finding_query_index(self) -> None:
        with self._lock:
            self.connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_findings_revision_identity "
                "ON findings(revision_id, startpoint, endpoint, path_group, analysis_type, corner, slack_ns)"
            )
            self.connection.commit()

    def new_violations(self, baseline_revision: str, candidate_revision: str) -> dict[str, Any]:
        with self._lock:
            revisions = {
                row["revision_id"]: dict(row) for row in self.connection.execute(
                    "SELECT * FROM revisions WHERE revision_id IN (?, ?)", (baseline_revision, candidate_revision)
                )
            }
            baseline, candidate = revisions.get(baseline_revision), revisions.get(candidate_revision)
            if not baseline or not candidate:
                raise KeyError("both revisions must exist")
            if baseline["design_id"] != candidate["design_id"]:
                return {"comparability": "INCOMPARABLE", "findings": []}
            if any(baseline[field] != candidate[field] for field in ("liberty_hash", "sdc_hash")):
                return {"comparability": "CONDITION_CHANGED", "findings": []}
            if any(baseline[field] != candidate[field] for field in ("tool_version", "parser_version")):
                return {"comparability": "TOOL_CHANGED", "findings": []}
            rows = self.connection.execute(
                "SELECT c.startpoint, c.endpoint, c.path_group, c.analysis_type, c.corner, c.slack_ns "
                "FROM findings c WHERE c.revision_id = ? AND c.slack_ns < 0 AND NOT EXISTS ("
                "SELECT 1 FROM findings b WHERE b.revision_id = ? AND b.startpoint = c.startpoint "
                "AND b.endpoint = c.endpoint AND b.path_group = c.path_group "
                "AND b.analysis_type = c.analysis_type AND b.corner = c.corner AND b.slack_ns < 0) "
                "ORDER BY c.slack_ns ASC, c.startpoint ASC, c.endpoint ASC, c.path_group ASC, "
                "c.analysis_type ASC, c.corner ASC",
                (candidate_revision, baseline_revision),
            ).fetchall()
            return {"comparability": "COMPARABLE", "findings": [dict(row) for row in rows]}
