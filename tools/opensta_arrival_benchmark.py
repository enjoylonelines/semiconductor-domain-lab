"""Measure fixed-wave arrivals against the selected one-host OpenSTA budget."""

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
WAVES = 4


def percentile(values: list[float], percentile_value: int) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(len(ordered) * percentile_value / 100))]


class WaveGatedAdapter:
    """A reusable barrier makes each accepted wave actually overlap."""

    def __init__(self) -> None:
        self.gate = threading.Barrier(CAPACITY)
        self.events: list[dict[str, str | float | int]] = []
        self.lock = threading.Lock()

    def run(self, job_spec: JobSpec):
        self.gate.wait(timeout=2)
        def observe(pid: int, started_at: float) -> None:
            with self.lock:
                self.events.append({"kind": "started", "job_id": job_spec.job_id, "pid": pid, "at": started_at})
        adapter = OpenStaSubprocessAdapter(
            sta_path=STA_PATH, liberty_path=LIBERTY_PATH, fixture_dir=FIXTURE_DIR,
            timeout_seconds=2, process_observer=observe,
        )
        result = adapter.run(job_spec)
        with self.lock:
            self.events.append({"kind": "completed", "job_id": job_spec.job_id, "at": time.monotonic()})
        return result


def spec(job_id: str) -> JobSpec:
    return JobSpec(job_id, "tiny", "tiny", "normal", "TT", 0, "ns")


def main() -> None:
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    adapter = WaveGatedAdapter()
    service = JobService(
        Store(), max_workers=CAPACITY, max_attempts=1, adapter=adapter,
        resource_slots=CAPACITY, max_in_flight=CAPACITY, worker_id="single-host-arrival",
    )
    accepted_durations: list[float] = []
    rejected = 0
    rejected_persisted = 0
    wave_results: list[dict[str, object]] = []
    for wave in range(WAVES):
        submitted: dict[str, float] = {}
        accepted: list[str] = []
        for index in range(CAPACITY + 1):
            job_id = f"wave-{wave}-job-{index}"
            started = time.monotonic()
            try:
                service.submit(spec(job_id))
                submitted[job_id] = started
                accepted.append(job_id)
            except BackpressureError:
                rejected += 1
                rejected_persisted += int(service.get(job_id) is not None)
        completion_times: dict[str, float] = {}
        for job_id in accepted:
            service.futures[job_id].result(timeout=5)
            completion_times[job_id] = time.monotonic()
        durations = [completion_times[job_id] - submitted[job_id] for job_id in accepted]
        accepted_durations.extend(durations)
        starts = [event["at"] for event in adapter.events if event["kind"] == "started" and event["job_id"].startswith(f"wave-{wave}-")]
        completions = [event["at"] for event in adapter.events if event["kind"] == "completed" and event["job_id"].startswith(f"wave-{wave}-")]
        wave_results.append({
            "wave": wave + 1,
            "accepted": len(accepted),
            "rejected": CAPACITY + 1 - len(accepted),
            "all_succeeded": all(service.get(job_id)["status"] == "SUCCEEDED" for job_id in accepted),
            "controlled_child_overlap": len(starts) == CAPACITY and max(starts) < min(completions),
            "p95_end_to_end_seconds": percentile(durations, 95),
        })
    payload = {
        "synthetic": False,
        "scope": "four fixed arrival waves against single-host OpenSTA service budget",
        "profile": {"max_workers": CAPACITY, "max_in_flight": CAPACITY, "resource_slots": CAPACITY},
        "waves": wave_results,
        "accepted": len(accepted_durations),
        "rejected": rejected,
        "rejection_ratio": rejected / (len(accepted_durations) + rejected),
        "rejected_runs_persisted": rejected_persisted,
        "p50_end_to_end_seconds": percentile(accepted_durations, 50),
        "p95_end_to_end_seconds": percentile(accepted_durations, 95),
        "max_end_to_end_seconds": max(accepted_durations),
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
