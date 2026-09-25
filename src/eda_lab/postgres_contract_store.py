"""Bounded PostgreSQL challenger for the operating-profile decision."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterable

import psycopg


class PostgresContractStore:
    """Only the four storage contracts compared with the local SQLite profile."""

    def __init__(self, dsn: str):
        self.connection = psycopg.connect(dsn)

    def close(self) -> None:
        self.connection.close()

    def reset(self) -> None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS contract_findings")
            cursor.execute("DROP TABLE IF EXISTS contract_revisions")
            cursor.execute("DROP TABLE IF EXISTS contract_attempts")
            cursor.execute("DROP TABLE IF EXISTS contract_runs")
            cursor.execute("CREATE TABLE contract_runs (job_id text PRIMARY KEY, status text NOT NULL)")
            cursor.execute(
                "CREATE TABLE contract_attempts (job_id text REFERENCES contract_runs(job_id), attempt_no integer, "
                "status text NOT NULL, lease_token text, PRIMARY KEY(job_id, attempt_no))"
            )
            cursor.execute("CREATE TABLE contract_revisions (revision_id text PRIMARY KEY)")
            cursor.execute(
                "CREATE TABLE contract_findings (id bigserial PRIMARY KEY, revision_id text NOT NULL "
                "REFERENCES contract_revisions(revision_id), startpoint text NOT NULL)"
            )

    def claim_run(self, job_id: str, budget: int) -> str:
        """Return created, existing, or backpressured under one global advisory lock."""
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", (481516,))
            cursor.execute("SELECT 1 FROM contract_runs WHERE job_id = %s", (job_id,))
            if cursor.fetchone() is not None:
                return "existing"
            cursor.execute("SELECT count(*) FROM contract_runs WHERE status IN ('QUEUED', 'RUNNING')")
            if cursor.fetchone()[0] >= budget:
                return "backpressured"
            cursor.execute("INSERT INTO contract_runs(job_id, status) VALUES (%s, 'QUEUED')", (job_id,))
            return "created"

    def create_attempt(self, job_id: str, attempt_no: int, token: str) -> None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                "INSERT INTO contract_attempts(job_id, attempt_no, status, lease_token) VALUES (%s, %s, 'RUNNING', %s)",
                (job_id, attempt_no, token),
            )

    def terminal_attempt(self, job_id: str, attempt_no: int, token: str, status: str) -> bool:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute(
                "UPDATE contract_attempts SET status = %s WHERE job_id = %s AND attempt_no = %s "
                "AND status = 'RUNNING' AND lease_token = %s",
                (status, job_id, attempt_no, token),
            )
            return cursor.rowcount == 1

    def create_revision(self, revision_id: str) -> None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.execute("INSERT INTO contract_revisions(revision_id) VALUES (%s)", (revision_id,))

    def save_findings(self, revision_id: str, rows: Iterable[tuple[str | None]]) -> None:
        with self.connection.transaction(), self.connection.cursor() as cursor:
            cursor.executemany(
                "INSERT INTO contract_findings(revision_id, startpoint) VALUES (%s, %s)",
                [(revision_id, startpoint) for (startpoint,) in rows],
            )

    def finding_count(self, revision_id: str) -> int:
        with self.connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM contract_findings WHERE revision_id = %s", (revision_id,))
            return cursor.fetchone()[0]
