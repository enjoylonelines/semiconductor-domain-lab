"""Run the bounded central-PostgreSQL contract challenger."""

from __future__ import annotations

import json
import os
import statistics
import threading
import time

from eda_lab.postgres_contract_store import PostgresContractStore


DSN = os.environ["EDA_POSTGRES_DSN"]
BUDGET = 8


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * fraction))]


def main() -> None:
    schema = PostgresContractStore(DSN)
    schema.reset()
    schema.close()

    duplicate = [PostgresContractStore(DSN), PostgresContractStore(DSN)]
    barrier = threading.Barrier(2)
    duplicate_results: list[str] = []

    def submit_duplicate(store: PostgresContractStore) -> None:
        barrier.wait(timeout=2)
        duplicate_results.append(store.claim_run("duplicate", BUDGET))
        store.close()

    duplicate_threads = [threading.Thread(target=submit_duplicate, args=(store,)) for store in duplicate]
    for thread in duplicate_threads:
        thread.start()
    for thread in duplicate_threads:
        thread.join(timeout=3)

    submitters = [PostgresContractStore(DSN), PostgresContractStore(DSN)]
    gate = threading.Barrier(2)
    results: list[str] = []
    latencies: list[float] = []

    def submit_unique(store: PostgresContractStore, offset: int) -> None:
        gate.wait(timeout=2)
        for index in range(8):
            started = time.perf_counter()
            results.append(store.claim_run(f"unique-{offset + index}", BUDGET))
            latencies.append(time.perf_counter() - started)
        store.close()

    threads = [
        threading.Thread(target=submit_unique, args=(submitters[0], 0)),
        threading.Thread(target=submit_unique, args=(submitters[1], 8)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    owner_worker = PostgresContractStore(DSN)
    stale_worker = PostgresContractStore(DSN)
    owner_worker.create_attempt("duplicate", 1, "owner")
    worker_gate = threading.Barrier(2)
    terminal_results: dict[str, bool] = {}

    def terminal_write(label: str, store: PostgresContractStore, token: str, status: str) -> None:
        worker_gate.wait(timeout=2)
        terminal_results[label] = store.terminal_attempt("duplicate", 1, token, status)
        store.close()

    worker_threads = [
        threading.Thread(target=terminal_write, args=("owner", owner_worker, "owner", "SUCCEEDED")),
        threading.Thread(target=terminal_write, args=("stale", stale_worker, "stale", "FAILED")),
    ]
    for thread in worker_threads:
        thread.start()
    for thread in worker_threads:
        thread.join(timeout=3)

    worker = PostgresContractStore(DSN)
    worker.create_revision("r1")
    try:
        worker.save_findings("r1", [("valid",), (None,)])
    except Exception as exc:
        bulk_error = type(exc).__name__
    else:
        bulk_error = None
    bulk_count = worker.finding_count("r1")
    worker.close()

    print(json.dumps({
        "synthetic": True,
        "scope": "two API submitters, two logical workers, central PostgreSQL contract store",
        "budget": BUDGET,
        "duplicate_claims": sorted(duplicate_results),
        "unique_claims": {state: results.count(state) for state in sorted(set(results))},
        "owner_terminal_write": terminal_results["owner"],
        "stale_terminal_write": terminal_results["stale"],
        "invalid_bulk_error": bulk_error,
        "post_failure_finding_count": bulk_count,
        "submit_latency_seconds": {
            "p50": round(statistics.median(latencies), 6),
            "p95": round(percentile(latencies, 0.95), 6),
        },
    }, sort_keys=True))


if __name__ == "__main__":
    main()
