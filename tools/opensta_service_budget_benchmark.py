"""Verify that the measured single-host OpenSTA budget holds in JobService.

This uses the already measured eight-child local profile. It is deliberately a
single batch: eight accepted jobs, one rejected job, then one post-release job.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from eda_lab.models import JobSpec
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import BackpressureError, JobService
from eda_lab.store import Store


REPOSITORY_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPOSITORY_ROOT / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")
CAPACITY = 8


def spec(job_id: str) -> JobSpec:
    return JobSpec(job_id, "tiny", "tiny", "opensta-fixed-fixture-v1", "TT", 0, "ns")


class FirstBatchGatedAdapter:
    """Make the first capacity jobs reach child-process start together."""

    def __init__(self) -> None:
        self.events: list[dict[str, float | int | str]] = []
        self.lock = threading.Lock()
        self.first_batch = threading.Barrier(CAPACITY)
        self.arrivals = 0
        self.delegate = OpenStaSubprocessAdapter(
            sta_path=STA_PATH,
            liberty_path=LIBERTY_PATH,
            fixture_dir=FIXTURE_DIR,
            timeout_seconds=2,
            process_observer=self._observe_process_start,
        )

    def _observe_process_start(self, pid: int, started_at: float) -> None:
        with self.lock:
            self.events.append({"kind": "process_started", "pid": pid, "at": started_at})

    def run(self, job_spec: JobSpec):
        with self.lock:
            self.arrivals += 1
            first_batch_member = self.arrivals <= CAPACITY
        if first_batch_member:
            self.first_batch.wait(timeout=2)
        result = self.delegate.run(job_spec)
        with self.lock:
            self.events.append({"kind": "adapter_completed", "job_id": job_spec.job_id, "at": time.monotonic()})
        return result


def main() -> None:
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    adapter = FirstBatchGatedAdapter()
    store = Store()
    service = JobService(
        store,
        max_workers=CAPACITY,
        max_attempts=1,
        adapter=adapter,
        resource_slots=CAPACITY,
        max_in_flight=CAPACITY,
        worker_id="single-host-capacity-benchmark",
    )
    accepted = [f"budget-{index}" for index in range(CAPACITY)]
    for job_id in accepted:
        service.submit(spec(job_id))
    rejected_job_id = "budget-rejected"
    try:
        service.submit(spec(rejected_job_id))
        rejected = False
        rejection = None
    except BackpressureError as exc:
        rejected = True
        rejection = str(exc)

    for job_id in accepted:
        service.futures[job_id].result(timeout=5)

    post_release_job_id = "budget-after-release"
    service.submit(spec(post_release_job_id))
    service.futures[post_release_job_id].result(timeout=5)
    starts = [event["at"] for event in adapter.events if event["kind"] == "process_started"]
    first_completions = [event["at"] for event in adapter.events if event["kind"] == "adapter_completed" and event["job_id"] in accepted]
    states = {job_id: service.get(job_id)["status"] for job_id in (*accepted, post_release_job_id)}
    payload = {
        "synthetic": False,
        "scope": "single-host JobService OpenSTA budget enforcement",
        "profile": {"max_workers": CAPACITY, "max_in_flight": CAPACITY, "resource_slots": CAPACITY},
        "accepted_jobs": accepted,
        "rejected_job": {"job_id": rejected_job_id, "rejected": rejected, "reason": rejection, "stored_run": service.get(rejected_job_id)},
        "post_release_job": {"job_id": post_release_job_id, "status": states[post_release_job_id]},
        "statuses": states,
        "process_events": adapter.events,
        "controlled_first_batch_overlap": (
            len(starts) >= CAPACITY
            and max(starts[:CAPACITY]) < min(first_completions)
        ),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
