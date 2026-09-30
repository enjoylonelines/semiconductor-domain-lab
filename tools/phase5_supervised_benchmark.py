"""Submit calibrated Heavy Runs and measure their supervised terminal convergence."""

from __future__ import annotations

import argparse
import json
import os
import time
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.service import JobService


TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("EDA_POSTGRES_TEST_DSN"))
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--corner", default="tt_025C_1v80")
    parser.add_argument("--timeout-seconds", type=float, default=600)
    args = parser.parse_args()
    if not args.dsn:
        raise SystemExit("set EDA_POSTGRES_TEST_DSN or pass --dsn")
    if args.runs < 1:
        raise SystemExit("--runs must be positive")

    store = PostgresStore(args.dsn)
    service = JobService(
        store,
        max_workers=1,
        max_attempts=1,
        max_in_flight=args.runs + 1,
        worker_id="phase5-submit",
        execution_mode="external",
    )
    prefix = f"phase5-heavy-{uuid4().hex}"
    jobs = [f"{prefix}-{index:02d}" for index in range(args.runs)]
    submitted_at = time.monotonic()
    try:
        submit_latencies = []
        for job_id in jobs:
            started = time.monotonic()
            service.submit(JobSpec(job_id, "picorv32x64", "research", "opensta_setup_max", args.corner, 0, "ns"))
            submit_latencies.append(time.monotonic() - started)
        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            runs = [store.get_run(job_id) for job_id in jobs]
            if all(run is not None and run["status"] in TERMINAL for run in runs):
                completed_at = time.monotonic()
                print(json.dumps({
                    "environment": "bounded same-VM Linux containers; one Host Agent; calibrated Heavy OpenSTA",
                    "corner": args.corner,
                    "runs": args.runs,
                    "elapsed_seconds": round(completed_at - submitted_at, 6),
                    "throughput_runs_per_second": round(args.runs / (completed_at - submitted_at), 6),
                    "submit_latency_seconds": [round(value, 6) for value in submit_latencies],
                    "terminal": [{
                        "job_id": run["job_id"],
                        "status": run["status"],
                        "trust_status": run["trust_status"],
                        "liberty_sha256": run["provenance"].get("liberty_sha256"),
                        "netlist_sha256": run["provenance"].get("netlist_sha256"),
                        "script_sha256": run["provenance"].get("script_sha256"),
                    } for run in runs],
                }, sort_keys=True))
                return
            time.sleep(0.25)
        raise SystemExit(f"timed out after {args.timeout_seconds}s waiting for {jobs}")
    finally:
        service.close()
        store.close()


if __name__ == "__main__":
    main()
