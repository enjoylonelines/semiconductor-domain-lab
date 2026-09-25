"""Verify client-side 429 retry against the real measured OpenSTA service profile."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from eda_lab.api import ApiHandler, create_server
from eda_lab.client import RetryingJobClient
from eda_lab.models import JobSpec
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import JobService
from eda_lab.store import Store


REPOSITORY_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPOSITORY_ROOT / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")
CAPACITY = 8


def spec(job_id: str) -> JobSpec:
    return JobSpec(job_id, "tiny", "tiny", "normal", "TT", 0, "ns")


class FirstBatchGatedAdapter:
    def __init__(self) -> None:
        self.gate = threading.Barrier(CAPACITY)
        self.arrivals = 0
        self.lock = threading.Lock()
        self.delegate = OpenStaSubprocessAdapter(
            sta_path=STA_PATH, liberty_path=LIBERTY_PATH, fixture_dir=FIXTURE_DIR, timeout_seconds=2,
        )

    def run(self, job_spec: JobSpec):
        with self.lock:
            self.arrivals += 1
            gated = self.arrivals <= CAPACITY
        if gated:
            self.gate.wait(timeout=2)
        return self.delegate.run(job_spec)


def main() -> None:
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    adapter = FirstBatchGatedAdapter()
    service = JobService(
        Store(), max_workers=CAPACITY, max_attempts=1, adapter=adapter,
        resource_slots=CAPACITY, max_in_flight=CAPACITY,
        backpressure_retry_after_seconds=0.3, worker_id="single-host-client-retry",
    )
    ApiHandler.service = service
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for index in range(CAPACITY):
            service.submit(spec(f"fill-{index}"))
        delays: list[float] = []

        def sleep_and_record(delay: float) -> None:
            delays.append(delay)
            time.sleep(delay)

        client = RetryingJobClient(
            f"http://127.0.0.1:{server.server_port}", jitter_seconds=0,
            sleeper=sleep_and_record,
        )
        accepted = client.submit(spec("retried-client-job"))
        service.futures["retried-client-job"].result(timeout=5)
        for index in range(CAPACITY):
            service.futures[f"fill-{index}"].result(timeout=5)
        payload = {
            "synthetic": False,
            "scope": "real OpenSTA service profile client retry after HTTP 429",
            "profile": {"max_workers": CAPACITY, "max_in_flight": CAPACITY, "resource_slots": CAPACITY, "retry_after_ms": 300},
            "client_delays_seconds": delays,
            "client_response_job_id": accepted["job_id"],
            "fill_statuses": [service.get(f"fill-{index}")["status"] for index in range(CAPACITY)],
            "retried_job": service.get("retried-client-job")["status"],
        }
        print(json.dumps(payload, sort_keys=True))
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
