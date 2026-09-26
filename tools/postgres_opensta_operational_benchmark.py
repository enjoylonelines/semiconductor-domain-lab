"""Measure the central-PostgreSQL path with two submitter and two OpenSTA worker processes."""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from pathlib import Path
from queue import Empty
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import BackpressureError, JobService
from eda_lab.worker import PostgresWorker


DSN = os.environ["EDA_POSTGRES_TEST_DSN"]
FIXTURE_DIR = Path(__file__).parents[1] / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")
BUDGET = 8


def submitter(dsn, job_ids, gate, output):
    store = PostgresStore(dsn)
    service = JobService(store, max_workers=1, max_attempts=1, worker_id="api", max_in_flight=BUDGET, execution_mode="external")
    try:
        gate.wait(timeout=10)
        outcomes = []
        for job_id in job_ids:
            started = time.perf_counter()
            try:
                outcome = service.submit(JobSpec(job_id, "tiny", "research", "opensta_setup_max", "tt_025C_1v80", 0, "ns"))
                outcomes.append({"job_id": job_id, "status": outcome["status"], "submit_seconds": time.perf_counter() - started})
            except BackpressureError:
                outcomes.append({"job_id": job_id, "status": "BACKPRESSURED", "submit_seconds": time.perf_counter() - started})
        output.put({"kind": "submitter", "outcomes": outcomes})
    finally:
        service.close()


def worker(dsn, worker_id, output):
    store = PostgresStore(dsn)
    adapter = OpenStaSubprocessAdapter(sta_path=STA_PATH, liberty_path=LIBERTY_PATH, fixture_dir=FIXTURE_DIR, timeout_seconds=2)
    service = JobService(store, max_workers=4, max_attempts=1, adapter=adapter, resource_slots=4,
                         worker_id=worker_id, max_in_flight=BUDGET, execution_mode="external")
    try:
        completed = PostgresWorker(store, service).drain(concurrency=4)
        output.put({"kind": "worker", "worker_id": worker_id, "completed": completed})
    finally:
        service.close()


def main():
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA fixture is unavailable")
    prefix = f"pg-opensta-{uuid4().hex}"
    duplicate = f"{prefix}-duplicate"
    unique = [f"{prefix}-unique-{index}" for index in range(7)]
    batches = [[duplicate, *unique[:4]], [duplicate, *unique[4:]]]
    gate, output = mp.Barrier(2), mp.Queue()
    submitters = [mp.Process(target=submitter, args=(DSN, batch, gate, output)) for batch in batches]
    started = time.perf_counter()
    for process in submitters: process.start()
    for process in submitters: process.join(timeout=20)
    if any(process.exitcode != 0 for process in submitters):
        raise SystemExit(f"submitter failure: {[process.exitcode for process in submitters]}")
    submission = [output.get(timeout=3) for _ in submitters]
    workers = [mp.Process(target=worker, args=(DSN, f"worker-{index + 1}", output)) for index in range(2)]
    for process in workers: process.start()
    for process in workers: process.join(timeout=30)
    if any(process.exitcode != 0 for process in workers):
        raise SystemExit(f"worker failure: {[process.exitcode for process in workers]}")
    worker_results = [output.get(timeout=3) for _ in workers]
    store = PostgresStore(DSN)
    try:
        job_ids = [duplicate, *unique]
        runs = [store.get_run(job_id) for job_id in job_ids]
    finally:
        store.close()
    submit_outcomes = [item for result in submission for item in result["outcomes"]]
    print(json.dumps({
        "synthetic": False,
        "scope": "two submitter processes, two worker processes, eight real OpenSTA setup/max Runs, central PostgreSQL",
        "budget": BUDGET,
        "submitted": len(submit_outcomes),
        "created_or_existing": sum(item["status"] == "QUEUED" for item in submit_outcomes),
        "backpressured": sum(item["status"] == "BACKPRESSURED" for item in submit_outcomes),
        "unique_runs": len(job_ids),
        "run_statuses": {run["job_id"]: run["status"] for run in runs},
        "trust_statuses": {run["job_id"]: run["trust_status"] for run in runs},
        "worker_results": worker_results,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "submit_latencies_seconds": [round(item["submit_seconds"], 6) for item in submit_outcomes],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
