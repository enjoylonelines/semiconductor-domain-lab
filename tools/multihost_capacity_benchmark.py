"""Measure bounded logical multi-host SS Heavy capacity with host distribution."""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.service import JobService


TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED"}


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * q)]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dsn", default=os.environ.get("EDA_POSTGRES_TEST_DSN"))
    parser.add_argument("--runs", type=int, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--corner", default="ss_100C_1v60")
    parser.add_argument("--timeout-seconds", type=float, default=600)
    args = parser.parse_args()
    if not args.dsn:
        raise SystemExit("set EDA_POSTGRES_TEST_DSN or pass --dsn")

    store = PostgresStore(args.dsn, migrate=False)
    service = JobService(
        store,
        max_workers=1,
        max_attempts=1,
        max_in_flight=args.runs + 1,
        worker_id="multihost-capacity-submit",
        execution_mode="external",
    )
    prefix = f"mh-cap-{args.label}-{uuid4().hex}"
    jobs = [f"{prefix}-{index:03d}" for index in range(args.runs)]
    submit_latencies: list[float] = []
    begun = time.monotonic()
    try:
        for job_id in jobs:
            started = time.monotonic()
            service.submit(
                JobSpec(
                    job_id,
                    "picorv32x64",
                    "research",
                    "opensta_setup_max",
                    args.corner,
                    0,
                    "ns",
                )
            )
            submit_latencies.append(time.monotonic() - started)

        deadline = time.monotonic() + args.timeout_seconds
        while time.monotonic() < deadline:
            runs = [store.get_run(job_id) for job_id in jobs]
            if all(run is not None and run["status"] in TERMINAL for run in runs):
                elapsed = time.monotonic() - begun
                host_counts = Counter()
                attempt_status = Counter()
                provenance = Counter()
                for run in runs:
                    for attempt in run["attempts"]:
                        attempt_status[attempt["status"]] += 1
                        if attempt.get("execution_host_id"):
                            host_counts[attempt["execution_host_id"]] += 1
                    provenance[(
                        run["provenance"].get("liberty_sha256"),
                        run["provenance"].get("netlist_sha256"),
                        run["provenance"].get("script_sha256"),
                    )] += 1

                with store.connection.cursor() as cursor:
                    cursor.execute(
                        """SELECT status,count(*) AS n
                           FROM eda_execution_requests
                           WHERE job_id LIKE %s
                           GROUP BY status ORDER BY status""",
                        (prefix + "%",),
                    )
                    request_status = {row["status"]: row["n"] for row in cursor.fetchall()}
                    cursor.execute(
                        """SELECT count(*) AS n FROM eda_attempts
                           WHERE job_id LIKE %s
                             AND status='RUNNING'
                             AND lease_expires_at < extract(epoch from clock_timestamp())""",
                        (prefix + "%",),
                    )
                    expired_live = cursor.fetchone()["n"]

                print(json.dumps({
                    "label": args.label,
                    "scope": "same Docker VM; logical Host identities; fixed SS Heavy OpenSTA",
                    "runs": args.runs,
                    "elapsed_seconds": elapsed,
                    "throughput_runs_per_second": args.runs / elapsed,
                    "submit_latency_seconds": {
                        "p50": percentile(submit_latencies, 0.50),
                        "p95": percentile(submit_latencies, 0.95),
                        "p99": percentile(submit_latencies, 0.99),
                    },
                    "run_status": dict(Counter(run["status"] for run in runs)),
                    "trust_status": dict(Counter(run["trust_status"] for run in runs)),
                    "attempt_status": dict(attempt_status),
                    "execution_host_counts": dict(host_counts),
                    "execution_request_status": request_status,
                    "expired_live_attempts": expired_live,
                    "provenance_counts": [
                        {
                            "liberty_sha256": key[0],
                            "netlist_sha256": key[1],
                            "script_sha256": key[2],
                            "count": count,
                        }
                        for key, count in provenance.items()
                    ],
                }, sort_keys=True))
                return
            time.sleep(0.25)
        raise SystemExit(f"timed out after {args.timeout_seconds}s")
    finally:
        service.close()
        store.close()


if __name__ == "__main__":
    main()
