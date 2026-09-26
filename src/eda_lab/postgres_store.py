"""PostgreSQL-backed Run/Attempt store for the operational candidate."""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .store import InFlightBudgetExhausted


class PostgresStore:
    """A Store-compatible central database; schema creation is non-destructive."""

    def __init__(self, dsn: str, now=None):
        # Read methods must not leave idle transactions open. State mutations below
        # use explicit transactions so their atomicity remains visible in the code.
        self.connection = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
        self._lock = threading.RLock()
        self._now = now or time.time
        self._closed = False
        self._migrate()

    def _migrate(self) -> None:
        with self.connection.transaction(), self.connection.cursor() as c:
            c.execute("""
            CREATE TABLE IF NOT EXISTS eda_runs (
              job_id text PRIMARY KEY, design_id text NOT NULL, ip_family text NOT NULL, flow_name text NOT NULL,
              status text NOT NULL, parse_status text NOT NULL, check_status text NOT NULL,
              completeness text NOT NULL DEFAULT 'unknown', semantic_status text NOT NULL DEFAULT 'UNKNOWN',
              provenance_status text NOT NULL DEFAULT 'UNKNOWN', trust_status text NOT NULL DEFAULT 'UNKNOWN',
              provenance jsonb NOT NULL DEFAULT '{}'::jsonb, artifact_path text, error text, spec_hash text,
              spec_payload jsonb, updated_at double precision NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS eda_metrics (job_id text PRIMARY KEY REFERENCES eda_runs(job_id), payload jsonb NOT NULL);
            CREATE TABLE IF NOT EXISTS eda_attempts (
              job_id text NOT NULL REFERENCES eda_runs(job_id), attempt_no integer NOT NULL, status text NOT NULL,
              error_type text, error text, artifact_path text, retry_class text, started_at double precision NOT NULL DEFAULT 0,
              updated_at double precision NOT NULL DEFAULT 0, lease_owner text, lease_token text,
              lease_expires_at double precision, heartbeat_at double precision, process_pid integer, process_started_at double precision,
              PRIMARY KEY(job_id, attempt_no));
            CREATE TABLE IF NOT EXISTS eda_metric_rows (id bigserial PRIMARY KEY, job_id text NOT NULL REFERENCES eda_runs(job_id), metric_name text NOT NULL, stage text NOT NULL, corner text NOT NULL, value double precision NOT NULL, unit text NOT NULL);
            CREATE INDEX IF NOT EXISTS idx_eda_metric_rows_stage_corner ON eda_metric_rows(stage, corner, metric_name);
            CREATE TABLE IF NOT EXISTS eda_revisions (revision_id text PRIMARY KEY, design_id text NOT NULL, source_revision text NOT NULL, liberty_hash text NOT NULL, sdc_hash text NOT NULL, tool_version text NOT NULL, parser_version text NOT NULL);
            CREATE TABLE IF NOT EXISTS eda_findings (id bigserial PRIMARY KEY, revision_id text NOT NULL REFERENCES eda_revisions(revision_id), run_id text NOT NULL, startpoint text NOT NULL, endpoint text NOT NULL, path_group text NOT NULL, analysis_type text NOT NULL, corner text NOT NULL, slack_ns double precision NOT NULL);
            """)

    def close(self) -> None:
        with self._lock:
            if not self._closed:
                self.connection.close()
                self._closed = True

    def now(self) -> float: return self._now()

    def create_run(self, job_id, design_id, ip_family, flow_name, spec_hash=None, max_in_flight=None, spec_payload=None) -> bool:
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            if max_in_flight is not None:
                c.execute("SELECT pg_advisory_xact_lock(%s)", (481516,))
                c.execute("SELECT 1 FROM eda_runs WHERE job_id = %s", (job_id,))
                if c.fetchone(): return False
                c.execute("SELECT count(*) AS n FROM eda_runs WHERE status IN ('QUEUED', 'RUNNING')")
                if c.fetchone()["n"] >= max_in_flight: raise InFlightBudgetExhausted()
            c.execute("""INSERT INTO eda_runs(job_id, design_id, ip_family, flow_name, status, parse_status, check_status, provenance, spec_hash, spec_payload, updated_at)
                         VALUES (%s,%s,%s,%s,'QUEUED','NOT_STARTED','UNKNOWN','{}'::jsonb,%s,%s::jsonb,%s)
                         ON CONFLICT (job_id) DO NOTHING""", (job_id, design_id, ip_family, flow_name, spec_hash, json.dumps(spec_payload) if spec_payload else None, self.now()))
            return c.rowcount == 1

    def update_run(self, job_id: str, **fields: Any) -> None:
        allowed = {"status","parse_status","check_status","completeness","semantic_status","provenance_status","trust_status","provenance","artifact_path","error"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields: return
        fields["updated_at"] = self.now()
        values = [json.dumps(v) if k == "provenance" else v for k,v in fields.items()]
        assignments = ", ".join(f"{k} = %s" + ("::jsonb" if k == "provenance" else "") for k in fields)
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            c.execute(f"UPDATE eda_runs SET {assignments} WHERE job_id = %s", (*values, job_id))

    def get_run(self, job_id: str) -> dict | None:
        with self._lock, self.connection.cursor() as c:
            c.execute("SELECT * FROM eda_runs WHERE job_id=%s", (job_id,)); result = c.fetchone()
            if not result: return None
            c.execute("SELECT payload FROM eda_metrics WHERE job_id=%s", (job_id,)); metric = c.fetchone()
            c.execute("SELECT * FROM eda_attempts WHERE job_id=%s ORDER BY attempt_no", (job_id,)); result["attempts"] = c.fetchall()
            result["metrics"] = metric["payload"] if metric else None
            return result

    def claim_next_run(self, worker_id: str) -> dict | None:
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            c.execute("""WITH candidate AS (SELECT job_id FROM eda_runs WHERE status='QUEUED' ORDER BY updated_at FOR UPDATE SKIP LOCKED LIMIT 1)
                         UPDATE eda_runs r SET status='RUNNING', updated_at=%s FROM candidate WHERE r.job_id=candidate.job_id RETURNING r.spec_payload""", (self.now(),))
            row = c.fetchone()
            return row["spec_payload"] if row else None

    def record_attempt(self, job_id, attempt_no, status, *, error_type=None, error=None, artifact_path=None, retry_class=None):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            now=self.now(); c.execute("""INSERT INTO eda_attempts(job_id,attempt_no,status,error_type,error,artifact_path,retry_class,started_at,updated_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(job_id,attempt_no) DO UPDATE SET status=EXCLUDED.status,error_type=EXCLUDED.error_type,error=EXCLUDED.error,artifact_path=COALESCE(EXCLUDED.artifact_path,eda_attempts.artifact_path),retry_class=EXCLUDED.retry_class,updated_at=EXCLUDED.updated_at""", (job_id,attempt_no,status,error_type,error,artifact_path,retry_class,now,now))

    def acquire_attempt_lease(self, job_id, attempt_no, owner, token, ttl_seconds):
        now=self.now()
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            c.execute("UPDATE eda_attempts SET lease_owner=%s,lease_token=%s,heartbeat_at=%s,lease_expires_at=%s,updated_at=%s WHERE job_id=%s AND attempt_no=%s AND status='RUNNING' AND (lease_expires_at IS NULL OR lease_expires_at < %s)", (owner,token,now,now+ttl_seconds,now,job_id,attempt_no,now)); return c.rowcount==1

    def heartbeat_attempt(self, job_id, attempt_no, token, ttl_seconds):
        now=self.now()
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            c.execute("UPDATE eda_attempts SET heartbeat_at=%s,lease_expires_at=%s,updated_at=%s WHERE job_id=%s AND attempt_no=%s AND status='RUNNING' AND lease_token=%s AND lease_expires_at >= %s", (now,now+ttl_seconds,now,job_id,attempt_no,token,now)); return c.rowcount==1

    def record_attempt_process(self, job_id, attempt_no, token, pid, started_at):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            c.execute("UPDATE eda_attempts SET process_pid=%s,process_started_at=%s,updated_at=%s WHERE job_id=%s AND attempt_no=%s AND status='RUNNING' AND lease_token=%s", (pid,started_at,self.now(),job_id,attempt_no,token)); return c.rowcount==1

    def transition_attempt(self, job_id, attempt_no, token, status, *, error_type=None, error=None, artifact_path=None, retry_class=None):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c:
            c.execute("UPDATE eda_attempts SET status=%s,error_type=%s,error=%s,artifact_path=COALESCE(%s,artifact_path),retry_class=%s,updated_at=%s WHERE job_id=%s AND attempt_no=%s AND status='RUNNING' AND lease_token=%s", (status,error_type,error,artifact_path,retry_class,self.now(),job_id,attempt_no,token)); return c.rowcount==1

    def list_expired_leased_attempts(self, now=None):
        with self._lock, self.connection.cursor() as c:
            c.execute("SELECT job_id,attempt_no FROM eda_attempts WHERE status='RUNNING' AND lease_token IS NOT NULL AND lease_expires_at < %s ORDER BY job_id,attempt_no", (self.now() if now is None else now,)); return [(r["job_id"],r["attempt_no"]) for r in c.fetchall()]

    def list_stale_running(self, cutoff):
        with self._lock, self.connection.cursor() as c:
            c.execute("SELECT job_id FROM eda_runs WHERE status='RUNNING' AND updated_at <= %s", (cutoff,)); ids=[r["job_id"] for r in c.fetchall()]
        return [r for i in ids if (r:=self.get_run(i))]

    def save_metrics(self, job_id, payload):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c: c.execute("INSERT INTO eda_metrics(job_id,payload) VALUES(%s,%s::jsonb) ON CONFLICT(job_id) DO UPDATE SET payload=EXCLUDED.payload", (job_id,json.dumps(payload)))

    def save_metric_rows(self, rows):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c: c.executemany("INSERT INTO eda_metric_rows(job_id,metric_name,stage,corner,value,unit) VALUES(%s,%s,%s,%s,%s,%s)", rows)

    def query_metric_summary(self, stage, corner, metric_name):
        with self._lock, self.connection.cursor() as c:
            c.execute("SELECT count(*) AS count,min(value) AS min_value,max(value) AS max_value,avg(value) AS avg_value FROM eda_metric_rows WHERE stage=%s AND corner=%s AND metric_name=%s", (stage,corner,metric_name)); row=c.fetchone(); return row if row and row["count"] else None

    def create_revision(self, revision_id, design_id, source_revision, liberty_hash, sdc_hash, tool_version, parser_version):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c: c.execute("INSERT INTO eda_revisions VALUES(%s,%s,%s,%s,%s,%s,%s)", (revision_id,design_id,source_revision,liberty_hash,sdc_hash,tool_version,parser_version))

    def save_findings(self, revision_id, findings):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c: c.executemany("INSERT INTO eda_findings(revision_id,run_id,startpoint,endpoint,path_group,analysis_type,corner,slack_ns) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)", [(revision_id,*f) for f in findings])

    def has_finding_query_index(self):
        with self._lock, self.connection.cursor() as c: c.execute("SELECT 1 FROM pg_indexes WHERE indexname='idx_eda_findings_revision_identity'"); return c.fetchone() is not None

    def create_finding_query_index(self):
        with self._lock, self.connection.transaction(), self.connection.cursor() as c: c.execute("CREATE INDEX IF NOT EXISTS idx_eda_findings_revision_identity ON eda_findings(revision_id,startpoint,endpoint,path_group,analysis_type,corner,slack_ns)")

    def new_violations(self, baseline_revision, candidate_revision):
        with self._lock, self.connection.cursor() as c:
            c.execute("SELECT * FROM eda_revisions WHERE revision_id IN (%s,%s)", (baseline_revision,candidate_revision)); revisions={r["revision_id"]:r for r in c.fetchall()}; b=revisions.get(baseline_revision); a=revisions.get(candidate_revision)
            if not b or not a: raise KeyError("both revisions must exist")
            if b["design_id"] != a["design_id"]: return {"comparability":"INCOMPARABLE","findings":[]}
            if any(b[x]!=a[x] for x in ("liberty_hash","sdc_hash")): return {"comparability":"CONDITION_CHANGED","findings":[]}
            if any(b[x]!=a[x] for x in ("tool_version","parser_version")): return {"comparability":"TOOL_CHANGED","findings":[]}
            c.execute("""SELECT c.startpoint,c.endpoint,c.path_group,c.analysis_type,c.corner,c.slack_ns FROM eda_findings c WHERE c.revision_id=%s AND c.slack_ns < 0 AND NOT EXISTS (SELECT 1 FROM eda_findings b WHERE b.revision_id=%s AND b.startpoint=c.startpoint AND b.endpoint=c.endpoint AND b.path_group=c.path_group AND b.analysis_type=c.analysis_type AND b.corner=c.corner AND b.slack_ns < 0) ORDER BY c.slack_ns,c.startpoint,c.endpoint,c.path_group,c.analysis_type,c.corner""", (candidate_revision,baseline_revision)); return {"comparability":"COMPARABLE","findings":c.fetchall()}
