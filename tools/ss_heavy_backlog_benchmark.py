"""Measure PostgreSQL coordination under a fixed SS Heavy execution capacity.

The benchmark changes backlog size only. It assumes a separately started Host
Agent and eight Supervisors that all target the supplied host_id. It does not
start Kafka and does not change execution capacity.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import statistics
import time
from collections import Counter
from uuid import uuid4

import psycopg
from psycopg.rows import dict_row

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.service import BackpressureError, IdempotencyConflict, JobService

EXPECTED = {
    "corner": "ss_100C_1v60",
    "liberty_sha256": "9b24f0db3967ac67b4cae1f74bb480fd47922d18d0ed577e3c121739b412c361",
    "netlist_sha256": "b3f09a42b23a9ff84c0084d4d284a9f8f5830b4c50f4972d68f59a18ea0938ce",
    "script_sha256": "cad5237c39e914222b23d6f30a86c6c34d5782bad5480dc7c8714607fb2688a1",
}


def percentile(values: list[float], pct: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil((pct / 100) * len(ordered)) - 1)
    return ordered[rank]


def summary(values: list[float]) -> dict[str, float | None]:
    return {
        "p50": statistics.median(values) if values else None,
        "p95": percentile(values, 95),
        "p99": percentile(values, 99),
        "max": max(values) if values else None,
    }


def db_counters(connection) -> dict:
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT xact_commit, xact_rollback, deadlocks
               FROM pg_stat_database WHERE datname = current_database()"""
        )
        return dict(cursor.fetchone())


def sample_state(connection, prefix: str, host_id: str, supervisor_count: int) -> dict:
    like = prefix + "%"
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT status, count(*) AS n
               FROM eda_runs WHERE job_id LIKE %s GROUP BY status""",
            (like,),
        )
        run_counts = {row["status"]: row["n"] for row in cursor.fetchall()}
        cursor.execute(
            """SELECT e.status, count(*) AS n
               FROM eda_execution_requests e
               WHERE e.job_id LIKE %s AND e.host_id = %s
               GROUP BY e.status""",
            (like, host_id),
        )
        delivery_counts = {row["status"]: row["n"] for row in cursor.fetchall()}
        cursor.execute(
            """SELECT count(*) AS n FROM pg_stat_activity
               WHERE datname = current_database()"""
        )
        connections = cursor.fetchone()["n"]
        cursor.execute(
            """SELECT count(*) AS n FROM pg_stat_activity
               WHERE datname = current_database() AND wait_event_type = 'Lock'"""
        )
        lock_waits = cursor.fetchone()["n"]
    running = int(delivery_counts.get("RUNNING", 0))
    return {
        "at": time.time(),
        "run_queue_depth": int(run_counts.get("QUEUED", 0)),
        "run_running": int(run_counts.get("RUNNING", 0)),
        "delivery_queue_depth": int(delivery_counts.get("QUEUED", 0)),
        "delivery_claimed": int(delivery_counts.get("CLAIMED", 0)),
        "delivery_running": running,
        "execution_slot_fraction": min(running, supervisor_count) / supervisor_count,
        "connections": int(connections),
        "lock_waits": int(lock_waits),
    }


def final_rows(connection, prefix: str) -> dict:
    like = prefix + "%"
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT job_id, status, trust_status, provenance
               FROM eda_runs WHERE job_id LIKE %s ORDER BY job_id""",
            (like,),
        )
        runs = cursor.fetchall()
        cursor.execute(
            """SELECT job_id, count(*) AS n
               FROM eda_attempts WHERE job_id LIKE %s
               GROUP BY job_id HAVING count(*) > 1""",
            (like,),
        )
        duplicate_attempts = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """SELECT job_id, count(*) AS n
               FROM eda_execution_requests WHERE job_id LIKE %s
               GROUP BY job_id HAVING count(*) > 1""",
            (like,),
        )
        duplicate_deliveries = [dict(row) for row in cursor.fetchall()]
        cursor.execute(
            """SELECT e.job_id, e.status, e.created_at, e.claimed_at, e.supervisor_id, e.host_id
               FROM eda_execution_requests e
               WHERE e.job_id LIKE %s ORDER BY e.created_at""",
            (like,),
        )
        deliveries = cursor.fetchall()
        cursor.execute(
            """SELECT a.job_id, a.status, a.error_type, a.error,
                      a.lease_expires_at, a.heartbeat_at
               FROM eda_attempts a WHERE a.job_id LIKE %s ORDER BY a.job_id, a.attempt_no""",
            (like,),
        )
        attempts = cursor.fetchall()
    return {
        "runs": runs,
        "duplicate_attempts": duplicate_attempts,
        "duplicate_deliveries": duplicate_deliveries,
        "deliveries": deliveries,
        "attempts": attempts,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("EDA_POSTGRES_DSN"))
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--host-id", default="ss-backlog-agent")
    parser.add_argument("--supervisors", type=int, default=8)
    parser.add_argument("--poll-seconds", type=float, default=0.25)
    parser.add_argument("--timeout-seconds", type=float, default=300)
    parser.add_argument("--revision", default="unrecorded")
    parser.add_argument("--image-revision", default="unrecorded")
    parser.add_argument("--include-samples", action="store_true")
    args = parser.parse_args()
    if not args.dsn:
        raise SystemExit("set EDA_POSTGRES_DSN or pass --dsn")
    if args.jobs < 1 or args.supervisors < 1:
        raise SystemExit("jobs and supervisors must be positive")

    prefix = f"ss-backlog-{args.jobs}-{uuid4().hex}-"
    store = PostgresStore(args.dsn)
    service = JobService(
        store,
        max_workers=1,
        max_attempts=1,
        worker_id="ss-backlog-api",
        max_in_flight=args.jobs,
        execution_mode="external",
    )
    monitor = psycopg.connect(args.dsn, row_factory=dict_row, autocommit=True)
    started_counters = db_counters(monitor)
    submit_latencies: list[float] = []
    submission_errors: list[dict] = []
    idempotency_conflicts = 0
    submitted_at: dict[str, float] = {}

    batch_started = time.monotonic()
    try:
        for index in range(args.jobs):
            job_id = f"{prefix}{index:04d}"
            spec = JobSpec(
                job_id,
                "picorv32x64-heavy",
                "research",
                "opensta_setup_max",
                EXPECTED["corner"],
                0,
                "ns",
            )
            begun = time.perf_counter()
            try:
                service.submit(spec)
                submitted_at[job_id] = time.time()
            except BackpressureError as exc:
                submission_errors.append({"job_id": job_id, "kind": "backpressure", "detail": str(exc)})
            except IdempotencyConflict as exc:
                idempotency_conflicts += 1
                submission_errors.append({"job_id": job_id, "kind": "idempotency", "detail": str(exc)})
            except Exception as exc:
                submission_errors.append({"job_id": job_id, "kind": type(exc).__name__, "detail": str(exc)})
            finally:
                submit_latencies.append(time.perf_counter() - begun)

        submission_finished = time.monotonic()
        samples = []
        deadline = time.monotonic() + args.timeout_seconds
        while True:
            sample = sample_state(monitor, prefix, args.host_id, args.supervisors)
            samples.append(sample)
            with monitor.cursor() as cursor:
                cursor.execute(
                    """SELECT count(*) AS n
                       FROM eda_runs
                       WHERE job_id LIKE %s
                         AND status NOT IN ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')""",
                    (prefix + "%",),
                )
                nonterminal = int(cursor.fetchone()["n"])
            if nonterminal == 0:
                break
            if time.monotonic() >= deadline:
                break
            time.sleep(args.poll_seconds)

        finished_at = time.monotonic()
        rows = final_rows(monitor, prefix)
        ended_counters = db_counters(monitor)
    finally:
        service.close()
        monitor.close()

    runs = rows["runs"]
    deliveries = rows["deliveries"]
    attempts = rows["attempts"]
    claim_latencies = [
        float(item["claimed_at"] - item["created_at"])
        for item in deliveries
        if item["claimed_at"] is not None
    ]
    queue_waits = [
        float(item["claimed_at"] - submitted_at[item["job_id"]])
        for item in deliveries
        if item["claimed_at"] is not None and item["job_id"] in submitted_at
    ]

    status_counts = Counter(item["status"] for item in runs)
    trust_counts = Counter(item["trust_status"] for item in runs)
    delivery_status_counts = Counter(item["status"] for item in deliveries)
    attempt_status_counts = Counter(item["status"] for item in attempts)
    provenance_mismatch = []
    for row in runs:
        provenance = row["provenance"] or {}
        mismatches = {
            key: {"expected": value, "observed": provenance.get(key)}
            for key, value in EXPECTED.items()
            if key != "corner" and provenance.get(key) != value
        }
        if mismatches:
            provenance_mismatch.append({"job_id": row["job_id"], "mismatches": mismatches})

    terminal = {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}
    nonterminal_runs = [row["job_id"] for row in runs if row["status"] not in terminal]
    unexpected_unavailable = [
        item["job_id"] for item in deliveries if item["status"] == "UNAVAILABLE"
    ]
    allowed_supervisors = {f"ss-backlog-supervisor-{index}" for index in range(1, args.supervisors + 1)}
    unexpected_supervisors = [
        {
            "job_id": item["job_id"],
            "supervisor_id": item["supervisor_id"],
            "host_id": item["host_id"],
        }
        for item in deliveries
        if item["supervisor_id"] not in allowed_supervisors
    ]
    lease_or_recovery_failures = [
        {"job_id": item["job_id"], "status": item["status"], "error_type": item["error_type"], "error": item["error"]}
        for item in attempts
        if item["error_type"] in {"worker_unavailable", "lease_expired", "recovery_required"}
    ]

    elapsed = finished_at - batch_started
    submit_elapsed = submission_finished - batch_started
    slot_samples = [item["execution_slot_fraction"] for item in samples]
    backlog_samples = [item for item in samples if item["run_queue_depth"] > 0]
    underfull_with_backlog = [
        item for item in backlog_samples if item["execution_slot_fraction"] < 1.0
    ]
    full_slot_samples = [item for item in samples if item["execution_slot_fraction"] == 1.0]
    output = {
        "scope": "SS Heavy backlog stress with fixed PostgreSQL coordination and fixed execution capacity",
        "metric_note": "delivery_claim_wait_seconds measures execution-request creation to Supervisor claim; it includes Supervisor availability and polling delay and is not PostgreSQL statement execution time.",
        "prefix": prefix,
        "jobs": args.jobs,
        "supervisors": args.supervisors,
        "host_id": args.host_id,
        "revision": args.revision,
        "image_revision": args.image_revision,
        "expected_provenance": EXPECTED,
        "submit": {
            "latency_seconds": summary(submit_latencies),
            "throughput_requests_per_second": args.jobs / submit_elapsed if submit_elapsed else None,
            "errors": submission_errors,
            "idempotency_conflicts": idempotency_conflicts,
        },
        "coordination": {
            "delivery_claim_wait_seconds": summary(claim_latencies),
            "queue_wait_seconds": summary(queue_waits),
            "connections_max": max((item["connections"] for item in samples), default=None),
            "lock_waits_max": max((item["lock_waits"] for item in samples), default=None),
            "lock_wait_sample_count": sum(item["lock_waits"] > 0 for item in samples),
            "lock_wait_with_run_backlog_count": sum(
                item["lock_waits"] > 0 and item["run_queue_depth"] > 0 for item in samples
            ),
            "xact_commit_delta": ended_counters["xact_commit"] - started_counters["xact_commit"],
            "xact_rollback_delta": ended_counters["xact_rollback"] - started_counters["xact_rollback"],
            "deadlock_delta": ended_counters["deadlocks"] - started_counters["deadlocks"],
            "db_xact_per_second_proxy": (
                (
                    ended_counters["xact_commit"] - started_counters["xact_commit"]
                    + ended_counters["xact_rollback"] - started_counters["xact_rollback"]
                ) / elapsed
                if elapsed else None
            ),
        },
        "queue_execution": {
            "makespan_seconds": elapsed,
            "run_queue_depth_max": max((item["run_queue_depth"] for item in samples), default=None),
            "delivery_queue_depth_max": max((item["delivery_queue_depth"] for item in samples), default=None),
            "execution_slot_fraction_mean": statistics.mean(slot_samples) if slot_samples else None,
            "execution_slot_fraction_max": max(slot_samples) if slot_samples else None,
            "sample_count": len(samples),
            "full_slot_sample_ratio": len(full_slot_samples) / len(samples) if samples else None,
            "backlog_sample_count": len(backlog_samples),
            "underfull_with_run_backlog_count": len(underfull_with_backlog),
            "underfull_with_run_backlog_samples": underfull_with_backlog[:10],
            **({"samples": samples} if args.include_samples else {}),
        },
        "correctness": {
            "run_statuses": dict(status_counts),
            "trust_statuses": dict(trust_counts),
            "delivery_statuses": dict(delivery_status_counts),
            "attempt_statuses": dict(attempt_status_counts),
            "duplicate_attempts": rows["duplicate_attempts"],
            "duplicate_deliveries": rows["duplicate_deliveries"],
            "unexpected_unavailable": unexpected_unavailable,
            "unexpected_supervisors": unexpected_supervisors,
            "lease_or_recovery_failures": lease_or_recovery_failures,
            "nonterminal_runs": nonterminal_runs,
            "provenance_mismatch": provenance_mismatch,
        },
    }
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()
