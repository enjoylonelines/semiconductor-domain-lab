"""Bounded Phase C comparison of PostgreSQL coordination and OpenSTA execution.

This is intentionally a single-host experiment. It reports whether increasing
worker processes shifts latency toward PostgreSQL claim coordination or toward
the actual OpenSTA execution slots; it does not claim horizontal scaling.
"""
from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import time
from pathlib import Path
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.runner import OpenStaSubprocessAdapter, SyntheticTimingAdapter
from eda_lab.service import JobService

ROOT = Path(__file__).parents[1]
FIXTURE_DIR = ROOT / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")


def p95(values: list[float]) -> float:
    return sorted(values)[max(0, (len(values) * 95 + 99) // 100 - 1)]


def worker(dsn: str, worker_id: str, workload: str, start, ready, output) -> None:
    store = PostgresStore(dsn)
    adapter = SyntheticTimingAdapter() if workload == "coordination" else OpenStaSubprocessAdapter(
        sta_path=STA_PATH, liberty_path=LIBERTY_PATH, fixture_dir=FIXTURE_DIR, timeout_seconds=2,
    )
    service = JobService(store, max_workers=1, max_attempts=1, adapter=adapter,
                         worker_id=worker_id, execution_mode="external")
    ready.put(worker_id)
    start.wait(10)
    claims: list[float] = []
    completed: list[str] = []
    try:
        while True:
            begun = time.perf_counter()
            payload = store.claim_next_run(worker_id)
            claims.append(time.perf_counter() - begun)
            if payload is None:
                break
            spec = service.spec_from_payload(payload)
            service.execute_claimed(spec).result(timeout=10)
            completed.append(spec.job_id)
        output.put({"worker_id": worker_id, "claim_latencies_seconds": claims, "completed": completed})
    finally:
        service.close()


def connection_count(store: PostgresStore) -> int:
    with store.connection.cursor() as cursor:
        cursor.execute("SELECT count(*) AS count FROM pg_stat_activity WHERE datname = current_database()")
        return cursor.fetchone()["count"]


def one_run(dsn: str, workload: str, worker_count: int, job_count: int) -> dict:
    prefix = f"phase-c-{workload}-{worker_count}-{uuid4().hex}"
    store = PostgresStore(dsn)
    api = JobService(store, max_workers=1, max_attempts=1, worker_id="benchmark-api",
                     max_in_flight=job_count, execution_mode="external")
    specs = [JobSpec(f"{prefix}-{index}", "tiny", "research", "opensta_setup_max", "tt_025C_1v80", 0, "ns")
             for index in range(job_count)]
    submission_latencies = []
    try:
        for spec in specs:
            begun = time.perf_counter()
            api.submit(spec)
            submission_latencies.append(time.perf_counter() - begun)
        context = mp.get_context("spawn")
        start, ready, output = context.Event(), context.Queue(), context.Queue()
        processes = [context.Process(target=worker, args=(dsn, f"worker-{index + 1}", workload, start, ready, output))
                     for index in range(worker_count)]
        for process in processes:
            process.start()
        for _ in processes:
            ready.get(timeout=10)
        sampled_connections = connection_count(store)
        begun = time.perf_counter()
        start.set()
        for process in processes:
            process.join(timeout=30)
        if any(process.exitcode != 0 for process in processes):
            raise RuntimeError(f"worker exit codes: {[process.exitcode for process in processes]}")
        worker_results = [output.get(timeout=3) for _ in processes]
        elapsed = time.perf_counter() - begun
        runs = [store.get_run(spec.job_id) for spec in specs]
        claim_latencies = [latency for result in worker_results for latency in result["claim_latencies_seconds"]]
        return {
            "workload": workload,
            "worker_count": worker_count,
            "job_count": job_count,
            "elapsed_seconds": elapsed,
            "throughput_runs_per_second": job_count / elapsed,
            "submit_latency_p50_seconds": statistics.median(submission_latencies),
            "submit_latency_p95_seconds": p95(submission_latencies),
            "claim_latency_p50_seconds": statistics.median(claim_latencies),
            "claim_latency_p95_seconds": p95(claim_latencies),
            "connection_count_at_start": sampled_connections,
            "worker_distribution": {item["worker_id"]: len(item["completed"]) for item in worker_results},
            "terminal_statuses": {run["status"]: sum(item["status"] == run["status"] for item in runs) for run in runs},
            "trusted_runs": sum(run["trust_status"] == "TRUSTED" for run in runs),
            "attempt_count": sum(len(run["attempts"]) for run in runs),
        }
    finally:
        api.close()


def summarize(samples: list[dict]) -> dict:
    first = samples[0]
    return {
        "workload": first["workload"], "worker_count": first["worker_count"], "job_count": first["job_count"],
        "repeats": len(samples),
        "elapsed_p50_seconds": statistics.median(item["elapsed_seconds"] for item in samples),
        "elapsed_p95_seconds": p95([item["elapsed_seconds"] for item in samples]),
        "throughput_p50_runs_per_second": statistics.median(item["throughput_runs_per_second"] for item in samples),
        "claim_latency_p50_seconds": statistics.median(item["claim_latency_p50_seconds"] for item in samples),
        "claim_latency_p95_seconds": p95([item["claim_latency_p95_seconds"] for item in samples]),
        "submit_latency_p50_seconds": statistics.median(item["submit_latency_p50_seconds"] for item in samples),
        "submit_latency_p95_seconds": p95([item["submit_latency_p95_seconds"] for item in samples]),
        "connection_count_at_start_max": max(item["connection_count_at_start"] for item in samples),
        "all_runs_succeeded": all(item["terminal_statuses"] == {"SUCCEEDED": item["job_count"]} for item in samples),
        "all_runs_trusted": all(item["trusted_runs"] == item["job_count"] for item in samples),
        "all_attempts_single": all(item["attempt_count"] == item["job_count"] for item in samples),
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("EDA_POSTGRES_TEST_DSN"))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--worker-counts", nargs="+", type=int, default=[1, 2, 4, 8])
    parser.add_argument("--coordination-jobs", type=int, default=32)
    parser.add_argument("--opensta-jobs", type=int, default=8)
    args = parser.parse_args()
    if not args.dsn:
        raise SystemExit("set EDA_POSTGRES_TEST_DSN or pass --dsn")
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("recorded local OpenSTA fixture is unavailable")
    results = []
    for workload, jobs in (("coordination", args.coordination_jobs), ("actual_opensta", args.opensta_jobs)):
        for count in args.worker_counts:
            results.append(summarize([one_run(args.dsn, workload, count, jobs) for _ in range(args.repeats)]))
    print(json.dumps({
        "scope": "single-host PostgreSQL coordination comparison; not horizontal scaling proof",
        "repeats": args.repeats, "worker_counts": args.worker_counts,
        "coordination_jobs": args.coordination_jobs, "opensta_jobs": args.opensta_jobs,
        "results": results,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
