"""Bounded PostgreSQL coordination stress with no OpenSTA execution cost.

The benchmark intentionally removes EDA compute so PostgreSQL create/claim/state
coordination can become the limiting resource. It is not an EDA throughput
benchmark and must not be mixed with SS Heavy capacity results.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import time
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.runner import SyntheticTimingAdapter
from eda_lab.service import JobService


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * q)]


def worker(dsn: str, worker_id: str, start, ready, output) -> None:
    store = PostgresStore(dsn, migrate=False)
    service = JobService(
        store,
        max_workers=1,
        max_attempts=1,
        adapter=SyntheticTimingAdapter(),
        worker_id=worker_id,
        execution_mode="external",
    )
    ready.put(worker_id)
    start.wait(30)
    claims: list[float] = []
    completed = 0
    errors: list[str] = []
    try:
        while True:
            begun = time.perf_counter()
            try:
                payload = store.claim_next_run(worker_id)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                break
            claims.append(time.perf_counter() - begun)
            if payload is None:
                break
            spec = service.spec_from_payload(payload)
            try:
                service.execute_claimed(spec).result(timeout=30)
            except Exception as exc:
                errors.append(f"{type(exc).__name__}: {exc}")
                break
            completed += 1
        output.put({
            "worker_id": worker_id,
            "claim_seconds": claims,
            "completed": completed,
            "errors": errors,
        })
    finally:
        service.close()


def db_snapshot(store: PostgresStore) -> dict:
    with store.connection.cursor() as cursor:
        cursor.execute("""
            SELECT
              count(*) FILTER (WHERE wait_event_type='Lock') AS lock_waits,
              count(*) FILTER (WHERE state='active') AS active,
              count(*) AS connections
            FROM pg_stat_activity
            WHERE datname=current_database()
        """)
        row = cursor.fetchone()
        return {
            "lock_waits": row["lock_waits"],
            "active_connections": row["active"],
            "connections": row["connections"],
        }


def one_run(dsn: str, worker_count: int, job_count: int) -> dict:
    prefix = f"pg-limit-{worker_count}-{job_count}-{uuid4().hex}"
    bootstrap = PostgresStore(dsn, migrate=True)
    bootstrap.close()

    store = PostgresStore(dsn, migrate=False)
    api = JobService(
        store,
        max_workers=1,
        max_attempts=1,
        worker_id="pg-limit-submit",
        max_in_flight=job_count + 1,
        execution_mode="external",
    )
    specs = [
        JobSpec(
            f"{prefix}-{index:05d}",
            "coordination",
            "research",
            "synthetic_coordination",
            "NA",
            0,
            "ns",
        )
        for index in range(job_count)
    ]
    submit_seconds: list[float] = []
    try:
        for spec in specs:
            begun = time.perf_counter()
            api.submit(spec)
            submit_seconds.append(time.perf_counter() - begun)

        ctx = mp.get_context("spawn")
        start = ctx.Event()
        ready = ctx.Queue()
        output = ctx.Queue()
        processes = [
            ctx.Process(
                target=worker,
                args=(dsn, f"pg-limit-worker-{index + 1}", start, ready, output),
            )
            for index in range(worker_count)
        ]
        for process in processes:
            process.start()
        for _ in processes:
            ready.get(timeout=30)

        start_snapshot = db_snapshot(store)
        begun = time.perf_counter()
        start.set()

        peak = dict(start_snapshot)
        while any(process.is_alive() for process in processes):
            snap = db_snapshot(store)
            for key in peak:
                peak[key] = max(peak[key], snap[key])
            time.sleep(0.01)

        for process in processes:
            process.join(timeout=10)
        elapsed = time.perf_counter() - begun
        exit_codes = [process.exitcode for process in processes]
        worker_results = [output.get(timeout=10) for _ in processes]
        claims = [
            value
            for result in worker_results
            for value in result["claim_seconds"]
        ]
        errors = [
            error
            for result in worker_results
            for error in result["errors"]
        ]

        with store.connection.cursor() as cursor:
            cursor.execute(
                "SELECT status,count(*) AS n FROM eda_runs "
                "WHERE job_id LIKE %s GROUP BY status ORDER BY status",
                (prefix + "%",),
            )
            status_counts = {row["status"]: row["n"] for row in cursor.fetchall()}
            cursor.execute(
                "SELECT count(*) AS n FROM eda_attempts "
                "WHERE job_id LIKE %s",
                (prefix + "%",),
            )
            attempts = cursor.fetchone()["n"]

        return {
            "worker_count": worker_count,
            "job_count": job_count,
            "elapsed_seconds": elapsed,
            "throughput_runs_per_second": job_count / elapsed,
            "submit_latency_seconds": {
                "p50": percentile(submit_seconds, 0.50),
                "p95": percentile(submit_seconds, 0.95),
                "p99": percentile(submit_seconds, 0.99),
            },
            "claim_call_latency_seconds": {
                "p50": percentile(claims, 0.50),
                "p95": percentile(claims, 0.95),
                "p99": percentile(claims, 0.99),
            },
            "db_peak": peak,
            "worker_completed": {
                result["worker_id"]: result["completed"]
                for result in worker_results
            },
            "errors": errors,
            "process_exit_codes": exit_codes,
            "run_status_counts": status_counts,
            "attempt_count": attempts,
        }
    finally:
        api.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("EDA_POSTGRES_TEST_DSN"))
    parser.add_argument("--workers", type=int, required=True)
    parser.add_argument("--jobs", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    args = parser.parse_args()
    if not args.dsn:
        raise SystemExit("set EDA_POSTGRES_TEST_DSN or pass --dsn")
    samples = [
        one_run(args.dsn, args.workers, args.jobs)
        for _ in range(args.repeats)
    ]
    print(json.dumps({
        "scope": "PostgreSQL coordination-only stress; synthetic execution; not EDA throughput",
        "workers": args.workers,
        "jobs": args.jobs,
        "repeats": args.repeats,
        "samples": samples,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
