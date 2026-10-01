import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any


class InFlightBudgetExhausted(RuntimeError):
    """A durable SQLite admission claim found the shared budget full."""


class Store:
    def __init__(self, path: str | Path = ":memory:", now=None):
        self._closed = False
        self.connection = sqlite3.connect(path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self._now = now or time.time
        self.connection.execute("PRAGMA foreign_keys=ON")
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
          process_pid INTEGER, process_started_at REAL, process_identity TEXT, process_group_id INTEGER, orphan_deadline REAL,
          execution_host_id TEXT, execution_host_epoch TEXT, execution_host_session TEXT, execution_id TEXT,
          recovery_owner TEXT, recovery_token TEXT, recovery_expires_at REAL,
          PRIMARY KEY(job_id, attempt_no)
        );
        CREATE TABLE IF NOT EXISTS host_sessions (
          session_id TEXT PRIMARY KEY, host_id TEXT NOT NULL, host_epoch TEXT NOT NULL,
          heartbeat_at REAL NOT NULL, lease_expires_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS hosts (
          host_id TEXT PRIMARY KEY, current_epoch TEXT NOT NULL, current_session_id TEXT NOT NULL,
          updated_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS execution_requests (
          execution_id TEXT PRIMARY KEY, job_id TEXT NOT NULL, attempt_no INTEGER NOT NULL,
          host_id TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL, created_at REAL NOT NULL,
          supervisor_id TEXT, claimed_at REAL, process_pid INTEGER, process_started_at REAL
        );
        CREATE TABLE IF NOT EXISTS execution_witnesses (
          execution_id TEXT PRIMARY KEY REFERENCES execution_requests(execution_id),
          kind TEXT NOT NULL, observed_at REAL NOT NULL, process_exit_code INTEGER,
          artifact_path TEXT, detail TEXT NOT NULL
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
        self._add_column_if_missing("attempts", "process_identity", "TEXT")
        self._add_column_if_missing("attempts", "process_group_id", "INTEGER")
        self._add_column_if_missing("attempts", "orphan_deadline", "REAL")
        self._add_column_if_missing("attempts", "execution_host_id", "TEXT")
        self._add_column_if_missing("attempts", "execution_host_epoch", "TEXT")
        self._add_column_if_missing("attempts", "execution_host_session", "TEXT")
        self._add_column_if_missing("attempts", "execution_id", "TEXT")
        self._add_column_if_missing("attempts", "recovery_owner", "TEXT")
        self._add_column_if_missing("attempts", "recovery_token", "TEXT")
        self._add_column_if_missing("attempts", "recovery_expires_at", "REAL")
        self._add_column_if_missing("execution_requests", "process_pid", "INTEGER")
        self._add_column_if_missing("execution_requests", "process_started_at", "REAL")
        self.connection.commit()

    def close(self) -> None:
        """Release this Store's SQLite connection. Safe to call more than once."""
        with self._lock:
            if not self._closed:
                self.connection.close()
                self._closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def __del__(self) -> None:
        # This is a last-resort guard for short-lived local callers. Services should
        # use close() so their executor has finished before the database closes.
        try:
            if hasattr(self, "_lock"):
                self.close()
        except BaseException:
            pass

    def _add_column_if_missing(self, table: str, column: str, definition: str) -> None:
        columns = {row["name"] for row in self.connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            self.connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def now(self) -> float:
        return self._now()

    def create_run(self, job_id: str, design_id: str, ip_family: str, flow_name: str, spec_hash: str | None = None,
                   max_in_flight: int | None = None, spec_payload: dict[str, Any] | None = None) -> bool:
        with self._lock:
            if max_in_flight is None:
                cursor = self.connection.execute(
                    "INSERT OR IGNORE INTO runs(job_id, design_id, ip_family, flow_name, status, parse_status, check_status, completeness, semantic_status, provenance_status, trust_status, provenance, spec_hash, updated_at) "
                    "VALUES (?, ?, ?, ?, 'QUEUED', 'NOT_STARTED', 'UNKNOWN', 'unknown', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', '{}', ?, ?)",
                    (job_id, design_id, ip_family, flow_name, spec_hash, self._now()),
                )
                self.connection.commit()
                return cursor.rowcount == 1
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                existing = self.connection.execute("SELECT 1 FROM runs WHERE job_id = ?", (job_id,)).fetchone()
                if existing is not None:
                    self.connection.commit()
                    return False
                in_flight = self.connection.execute(
                    "SELECT COUNT(*) FROM runs WHERE status IN ('QUEUED', 'RUNNING')"
                ).fetchone()[0]
                if in_flight >= max_in_flight:
                    raise InFlightBudgetExhausted()
                self.connection.execute(
                    "INSERT INTO runs(job_id, design_id, ip_family, flow_name, status, parse_status, check_status, completeness, semantic_status, provenance_status, trust_status, provenance, spec_hash, updated_at) "
                    "VALUES (?, ?, ?, ?, 'QUEUED', 'NOT_STARTED', 'UNKNOWN', 'unknown', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', '{}', ?, ?)",
                    (job_id, design_id, ip_family, flow_name, spec_hash, self._now()),
                )
                self.connection.commit()
                return True
            except Exception:
                if self.connection.in_transaction:
                    self.connection.rollback()
                raise

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

    def list_runs(self, status: str | None = None, limit: int = 50,
                  cursor: tuple[float, str] | None = None) -> list[dict[str, Any]]:
        """Return a stable page ordered by newest stored Run first."""
        clauses: list[str] = []
        parameters: list[Any] = []
        if status:
            clauses.append("status = ?")
            parameters.append(status)
        if cursor is not None:
            updated_at, job_id = cursor
            clauses.append("(updated_at < ? OR (updated_at = ? AND job_id < ?))")
            parameters.extend([updated_at, updated_at, job_id])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._lock:
            rows = self.connection.execute(
                f"SELECT job_id FROM runs{where} ORDER BY updated_at DESC, job_id DESC LIMIT ?",
                (*parameters, limit),
            ).fetchall()
        return [run for row in rows if (run := self.get_run(row["job_id"])) is not None]

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

    def record_attempt_process(self, job_id: str, attempt_no: int, token: str, pid: int, started_at: float,
                               *, process_identity: str | None = None, process_group_id: int | None = None,
                               orphan_deadline: float | None = None) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET process_pid = ?, process_started_at = ?, process_identity = ?, process_group_id = ?, orphan_deadline = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND lease_token = ?",
                (pid, started_at, process_identity, process_group_id, orphan_deadline, self._now(), job_id, attempt_no, token),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def start_host_session(self, host_id: str, host_epoch: str, session_id: str, ttl_seconds: float) -> None:
        now = self._now()
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                self.connection.execute(
                    "INSERT INTO host_sessions(session_id, host_id, host_epoch, heartbeat_at, lease_expires_at) VALUES (?, ?, ?, ?, ?)",
                    (session_id, host_id, host_epoch, now, now + ttl_seconds),
                )
                self.connection.execute(
                    "INSERT INTO hosts(host_id, current_epoch, current_session_id, updated_at) VALUES (?, ?, ?, ?) "
                    "ON CONFLICT(host_id) DO UPDATE SET current_epoch = excluded.current_epoch, "
                    "current_session_id = excluded.current_session_id, updated_at = excluded.updated_at",
                    (host_id, host_epoch, session_id, now),
                )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

    def heartbeat_host_session(self, session_id: str, ttl_seconds: float) -> bool:
        now = self._now()
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE host_sessions SET heartbeat_at = ?, lease_expires_at = ? WHERE session_id = ? "
                "AND EXISTS (SELECT 1 FROM hosts WHERE current_session_id = host_sessions.session_id)",
                (now, now + ttl_seconds, session_id),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def heartbeat_queued_execution_attempts(self, session_id: str, ttl_seconds: float) -> int:
        """Refresh only queued deliveries until a Supervisor owns their heartbeat."""
        now = self._now()
        with self._lock:
            cursor = self.connection.execute(
                """UPDATE attempts SET heartbeat_at = ?, lease_expires_at = ?, updated_at = ?
                   WHERE status = 'RUNNING' AND execution_host_session = ?
                     AND EXISTS (SELECT 1 FROM execution_requests e
                                 WHERE e.execution_id = attempts.execution_id AND e.status = 'QUEUED')
                     AND EXISTS (SELECT 1 FROM host_sessions s JOIN hosts h ON h.current_session_id = s.session_id
                                 WHERE s.session_id = ? AND s.lease_expires_at >= ?)""",
                (now, now + ttl_seconds, now, session_id, session_id, now),
            )
            self.connection.commit()
            return cursor.rowcount

    def record_attempt_execution(self, job_id: str, attempt_no: int, token: str, *, host_id: str,
                                 host_epoch: str, session_id: str, execution_id: str) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET execution_host_id = ?, execution_host_epoch = ?, execution_host_session = ?, "
                "execution_id = ?, updated_at = ? WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' "
                "AND lease_token = ? AND EXISTS (SELECT 1 FROM host_sessions s JOIN hosts h ON h.current_session_id = s.session_id "
                "WHERE s.session_id = ? AND s.host_id = ? AND s.host_epoch = ? AND s.lease_expires_at >= ?)",
                (host_id, host_epoch, session_id, execution_id, self._now(), job_id, attempt_no, token,
                 session_id, host_id, host_epoch, self._now()),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def enqueue_execution_request(self, execution_id: str, job_id: str, attempt_no: int, host_id: str, payload: dict) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "INSERT INTO execution_requests(execution_id,job_id,attempt_no,host_id,status,payload,created_at) VALUES(?,?,?,?,'QUEUED',?,?) ON CONFLICT(execution_id) DO NOTHING",
                (execution_id, job_id, attempt_no, host_id, json.dumps(payload, sort_keys=True), self._now()),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def claim_execution_request(self, host_id: str, supervisor_id: str) -> dict | None:
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                row = self.connection.execute(
                    "SELECT execution_id, job_id, attempt_no, payload FROM execution_requests WHERE host_id=? AND status='QUEUED' ORDER BY created_at LIMIT 1",
                    (host_id,),
                ).fetchone()
                if row is None:
                    self.connection.commit(); return None
                claimed = self.connection.execute(
                    "UPDATE execution_requests SET status='CLAIMED',supervisor_id=?,claimed_at=? WHERE execution_id=? AND status='QUEUED'",
                    (supervisor_id, self._now(), row["execution_id"]),
                )
                if claimed.rowcount != 1:
                    self.connection.rollback(); return None
                self.connection.commit()
                return {**dict(row), "payload": json.loads(row["payload"])}
            except Exception:
                self.connection.rollback(); raise

    def record_supervisor_process_started(self, execution_id: str, supervisor_id: str, pid: int) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE execution_requests SET process_pid=?,process_started_at=?,status='RUNNING' WHERE execution_id=? AND status='CLAIMED' AND supervisor_id=?",
                (pid, self._now(), execution_id, supervisor_id),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def record_termination_witness(self, execution_id: str, *, kind: str, process_exit_code: int | None, artifact_path: str | None, detail: str) -> bool:
        if kind not in {"PROCESS_EXITED", "RUNTIME_TERMINATED"}:
            raise ValueError("unsupported termination witness")
        with self._lock:
            cursor = self.connection.execute(
                "INSERT INTO execution_witnesses(execution_id,kind,observed_at,process_exit_code,artifact_path,detail) SELECT execution_id,?,?,?,?,? FROM execution_requests WHERE execution_id=? ON CONFLICT(execution_id) DO NOTHING",
                (kind, self._now(), process_exit_code, artifact_path, detail, execution_id),
            )
            if cursor.rowcount:
                self.connection.execute("UPDATE execution_requests SET status='COMPLETED' WHERE execution_id=? AND status IN ('CLAIMED','RUNNING')", (execution_id,))
            self.connection.commit()
            return cursor.rowcount == 1

    def get_termination_witness(self, execution_id: str | None) -> dict | None:
        if not execution_id:
            return None
        with self._lock:
            row = self.connection.execute("SELECT * FROM execution_witnesses WHERE execution_id=?", (execution_id,)).fetchone()
            return dict(row) if row else None

    def transition_attempt(self, job_id: str, attempt_no: int, token: str, status: str, *, error_type: str | None = None,
                           error: str | None = None, artifact_path: str | None = None, retry_class: str | None = None) -> bool:
        """Fence terminal state changes to the lease token that owns this Attempt."""
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET status = ?, error_type = ?, error = ?, artifact_path = COALESCE(?, artifact_path), "
                "retry_class = ?, updated_at = ? WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND lease_token = ? "
                "AND lease_expires_at >= ? AND (recovery_token IS NULL OR recovery_expires_at < ?)",
                (status, error_type, error, artifact_path, retry_class, self._now(), job_id, attempt_no, token, self._now(), self._now()),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def claim_recovery(self, job_id: str, attempt_no: int, owner: str, token: str, ttl_seconds: float) -> bool:
        now = self._now()
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET recovery_owner = ?, recovery_token = ?, recovery_expires_at = ?, updated_at = ? "
                "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND lease_expires_at < ? "
                "AND (recovery_token IS NULL OR recovery_expires_at < ?)",
                (owner, token, now + ttl_seconds, now, job_id, attempt_no, now, now),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def release_recovery_claim(self, job_id: str, attempt_no: int, token: str) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE attempts SET recovery_owner = NULL, recovery_token = NULL, recovery_expires_at = NULL, updated_at = ? "
                "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND recovery_token = ?",
                (self._now(), job_id, attempt_no, token),
            )
            self.connection.commit()
            return cursor.rowcount == 1

    def finalize_recovery(self, job_id: str, attempt_no: int, token: str, *, error_type: str, error: str) -> bool:
        now = self._now()
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                attempt = self.connection.execute(
                    "UPDATE attempts SET status = 'ABANDONED', error_type = ?, error = ?, retry_class = 'recovery_required', updated_at = ? "
                    "WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' AND recovery_token = ?",
                    (error_type, error, now, job_id, attempt_no, token),
                )
                if attempt.rowcount != 1:
                    self.connection.rollback()
                    return False
                run = self.connection.execute(
                    "UPDATE runs SET status = 'FAILED', error = ?, updated_at = ? WHERE job_id = ? AND status = 'RUNNING'",
                    (error, now, job_id),
                )
                if run.rowcount != 1:
                    self.connection.rollback()
                    return False
                self.connection.execute(
                    "UPDATE execution_requests SET status = 'UNAVAILABLE' "
                    "WHERE job_id = ? AND attempt_no = ? AND status IN ('QUEUED','CLAIMED','RUNNING')",
                    (job_id, attempt_no),
                )
                self.connection.commit()
                return True
            except Exception:
                self.connection.rollback()
                raise

    def finalize_attempt_and_run(self, job_id: str, attempt_no: int, token: str, attempt_status: str, run_status: str,
                                 *, error_type: str | None = None, error: str | None = None,
                                 artifact_path: str | None = None, retry_class: str | None = None,
                                 run_fields: dict[str, Any] | None = None,
                                 execution_owner: dict[str, str] | None = None) -> bool:
        """Commit a lease-fenced Attempt terminal state and its Run together."""
        now = self._now()
        fields = {key: value for key, value in (run_fields or {}).items() if key in {
            "parse_status", "check_status", "completeness", "semantic_status", "provenance_status",
            "trust_status", "provenance", "artifact_path", "error",
        }}
        fields.update({"status": run_status, "updated_at": now})
        if "error" not in fields:
            fields["error"] = error
        if artifact_path is not None and "artifact_path" not in fields:
            fields["artifact_path"] = artifact_path
        if "provenance" in fields:
            fields["provenance"] = json.dumps(fields["provenance"] or {}, sort_keys=True)
        assignments = ", ".join(f"{key} = ?" for key in fields)
        owner_clause = ""
        owner_values: list[Any] = []
        if execution_owner is not None:
            owner_clause = (
                " AND execution_host_id = ? AND execution_host_epoch = ? AND execution_host_session = ? "
                "AND EXISTS (SELECT 1 FROM host_sessions s JOIN hosts h ON h.current_session_id = s.session_id "
                "WHERE s.session_id = ? AND s.lease_expires_at >= ?)"
            )
            owner_values = [execution_owner["host_id"], execution_owner["host_epoch"], execution_owner["session_id"],
                            execution_owner["session_id"], now]
        with self._lock:
            self.connection.execute("BEGIN IMMEDIATE")
            try:
                attempt = self.connection.execute(
                    "UPDATE attempts SET status = ?, error_type = ?, error = ?, artifact_path = COALESCE(?, artifact_path), "
                    "retry_class = ?, updated_at = ? WHERE job_id = ? AND attempt_no = ? AND status = 'RUNNING' "
                    "AND lease_token = ? AND lease_expires_at >= ? AND (recovery_token IS NULL OR recovery_expires_at < ?)" + owner_clause,
                    (attempt_status, error_type, error, artifact_path, retry_class, now, job_id, attempt_no, token, now, now, *owner_values),
                )
                if attempt.rowcount != 1:
                    self.connection.rollback()
                    return False
                run = self.connection.execute(
                    f"UPDATE runs SET {assignments} WHERE job_id = ? AND status = 'RUNNING'", (*fields.values(), job_id)
                )
                if run.rowcount != 1:
                    self.connection.rollback()
                    return False
                self.connection.commit()
                return True
            except Exception:
                self.connection.rollback()
                raise

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
            try:
                self.connection.executemany(
                    "INSERT INTO findings(revision_id, run_id, startpoint, endpoint, path_group, analysis_type, corner, slack_ns) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    [(revision_id, *finding) for finding in findings],
                )
                self.connection.commit()
            except Exception:
                self.connection.rollback()
                raise

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
