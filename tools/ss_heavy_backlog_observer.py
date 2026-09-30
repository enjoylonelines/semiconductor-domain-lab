"""Observe one bounded SS Heavy backlog stage without changing execution capacity.

This tool wraps the existing supervised Heavy submission command and samples
PostgreSQL delivery state plus fixed Supervisor containers. It is evidence
collection for the PostgreSQL-vs-delivery decision; it does not tune the
workload, PostgreSQL, or Supervisor count.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import threading
import time
from statistics import median


def command(*args: str) -> str:
    return subprocess.check_output(args, text=True).strip()


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = round((len(ordered) - 1) * q)
    return ordered[index]


def pg_query(pg_container: str, pg_user: str, pg_db: str, sql: str) -> str:
    return command(
        "docker", "exec", pg_container,
        "psql", "-U", pg_user, "-d", pg_db, "-At", "-F", ",", "-c", sql,
    )


def sample(stop: threading.Event, rows: list[dict], names: list[str], pg_container: str, pg_user: str, pg_db: str) -> None:
    sql = """
    SELECT
      count(*) FILTER (WHERE wait_event_type='Lock'),
      count(*) FILTER (WHERE state='active'),
      count(*)
    FROM pg_stat_activity
    WHERE datname=current_database();
    SELECT
      count(*) FILTER (WHERE status='QUEUED'),
      count(*) FILTER (WHERE status='CLAIMED'),
      count(*) FILTER (WHERE status='RUNNING'),
      count(*) FILTER (WHERE status='COMPLETED'),
      count(*) FILTER (WHERE status='UNAVAILABLE')
    FROM eda_execution_requests;
    SELECT count(*)
    FROM eda_attempts
    WHERE status='RUNNING'
      AND lease_token IS NOT NULL
      AND lease_expires_at < extract(epoch from clock_timestamp());
    SELECT
      count(*) FILTER (WHERE status='QUEUED'),
      count(*) FILTER (WHERE status='RUNNING'),
      count(*) FILTER (WHERE status='SUCCEEDED'),
      count(*) FILTER (WHERE status='FAILED'),
      count(*) FILTER (WHERE status='CANCELLED')
    FROM eda_runs;
    """
    while not stop.wait(0.25):
        stats = command(
            "docker", "stats", "--no-stream", "--format", "{{json .}}", *names
        ).splitlines()
        raw = pg_query(pg_container, pg_user, pg_db, sql).splitlines()
        if len(raw) != 4:
            raise RuntimeError(f"unexpected PostgreSQL sample output: {raw}")
        locks, active, connections = (int(x) for x in raw[0].split(","))
        queued, claimed, running, completed, unavailable = (
            int(x) for x in raw[1].split(",")
        )
        expired = int(raw[2])
        run_queued, run_running, run_succeeded, run_failed, run_cancelled = (
            int(x) for x in raw[3].split(",")
        )
        rows.append({
            "at": time.time(),
            "lock_waits": locks,
            "active_connections": active,
            "connections": connections,
            "execution_requests": {
                "queued": queued,
                "claimed": claimed,
                "running": running,
                "completed": completed,
                "unavailable": unavailable,
            },
            "expired_running_attempt_leases": expired,
            "runs": {
                "queued": run_queued,
                "running": run_running,
                "succeeded": run_succeeded,
                "failed": run_failed,
                "cancelled": run_cancelled,
            },
            "containers": [json.loads(line) for line in stats if line],
        })


def delivery_rows(job_ids: list[str], pg_container: str, pg_user: str, pg_db: str) -> list[dict]:
    quoted = ",".join("'" + job_id.replace("'", "''") + "'" for job_id in job_ids)
    sql = f"""
    SELECT job_id,status,created_at,claimed_at,
           CASE WHEN claimed_at IS NULL THEN NULL ELSE claimed_at-created_at END
    FROM eda_execution_requests
    WHERE job_id IN ({quoted})
    ORDER BY created_at;
    """
    raw = pg_query(pg_container, pg_user, pg_db, sql)
    result = []
    for line in raw.splitlines():
        if not line:
            continue
        job_id, status, created_at, claimed_at, claim_seconds = line.split(",", 4)
        result.append({
            "job_id": job_id,
            "status": status,
            "created_at": float(created_at),
            "claimed_at": float(claimed_at) if claimed_at else None,
            "claim_latency_seconds": float(claim_seconds) if claim_seconds else None,
        })
    return result


def attempt_summary(job_ids: list[str], pg_container: str, pg_user: str, pg_db: str) -> dict:
    quoted = ",".join("'" + job_id.replace("'", "''") + "'" for job_id in job_ids)
    sql = f"""
    SELECT
      count(*),
      count(*) FILTER (WHERE status='SUCCEEDED'),
      count(*) FILTER (WHERE status='ABANDONED'),
      count(*) FILTER (WHERE status='RUNNING'),
      count(*) FILTER (WHERE recovery_token IS NOT NULL)
    FROM eda_attempts
    WHERE job_id IN ({quoted});
    """
    total, succeeded, abandoned, running, recovery = (
        int(x) for x in pg_query(pg_container, pg_user, pg_db, sql).split(",")
    )
    return {
        "attempts": total,
        "succeeded_attempts": succeeded,
        "abandoned_attempts": abandoned,
        "running_attempts": running,
        "attempts_with_recovery_claim": recovery,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--result-command", required=True)
    parser.add_argument("--supervisors", type=int, default=8)
    parser.add_argument("--supervisor-prefix", default="ss-scale-supervisor-")
    parser.add_argument("--postgres-container", default="eda-multihost-m1-postgres-1")
    parser.add_argument("--postgres-user", default="eda")
    parser.add_argument("--postgres-db", default="eda_m1")
    args = parser.parse_args()
    if args.runs < 1 or args.repeats < 1 or args.supervisors < 1:
        raise SystemExit("runs, repeats, and supervisors must be positive")

    names = [f"{args.supervisor_prefix}{index}" for index in range(1, args.supervisors + 1)]
    batches = []

    for repeat in range(1, args.repeats + 1):
        samples: list[dict] = []
        stop = threading.Event()
        thread = threading.Thread(
            target=sample,
            args=(stop, samples, names, args.postgres_container, args.postgres_user, args.postgres_db),
            daemon=True,
        )
        thread.start()
        started = time.perf_counter()
        output = subprocess.check_output(args.result_command, shell=True, text=True)
        observer_elapsed = time.perf_counter() - started
        stop.set()
        thread.join(2)

        result = json.loads(output.strip().splitlines()[-1])
        job_ids = [item["job_id"] for item in result["terminal"]]
        deliveries = delivery_rows(job_ids, args.postgres_container, args.postgres_user, args.postgres_db)
        claims = [
            row["claim_latency_seconds"]
            for row in deliveries
            if row["claim_latency_seconds"] is not None
        ]
        submit = [float(value) for value in result.get("submit_latency_seconds", [])]
        queue_wait = claims

        batches.append({
            "repeat": repeat,
            "observer_elapsed_seconds": observer_elapsed,
            "result": result,
            "delivery_rows": deliveries,
            "attempt_summary": attempt_summary(job_ids, args.postgres_container, args.postgres_user, args.postgres_db),
            "submit_latency": {
                "p50_seconds": median(submit) if submit else None,
                "p95_seconds": percentile(submit, 0.95),
                "p99_seconds": percentile(submit, 0.99),
            },
            "claim_latency": {
                "p50_seconds": median(claims) if claims else None,
                "p95_seconds": percentile(claims, 0.95),
                "p99_seconds": percentile(claims, 0.99),
            },
            "queue_wait": {
                "p50_seconds": median(queue_wait) if queue_wait else None,
                "p95_seconds": percentile(queue_wait, 0.95),
                "p99_seconds": percentile(queue_wait, 0.99),
            },
            "samples": samples,
        })

    print(json.dumps({
        "scope": "SS Heavy backlog arrival stress with fixed execution capacity",
        "runs": args.runs,
        "repeats": args.repeats,
        "supervisors": args.supervisors,
        "supervisor_prefix": args.supervisor_prefix,
        "postgres_container": args.postgres_container,
        "postgres_user": args.postgres_user,
        "postgres_db": args.postgres_db,
        "batches": batches,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
