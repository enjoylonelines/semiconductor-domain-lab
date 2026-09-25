"""Exercise the selected OpenSTA service budget through failure and recovery.

It is a bounded one-host experiment: an eight-job mixed batch, immediate
backpressure, a real child timeout, post-timeout admission, and a worker-loss
injection after a real child returns but before terminal persistence.
"""

from __future__ import annotations

import json
import shutil
import tempfile
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


def spec(job_id: str, flow_name: str = "normal") -> JobSpec:
    return JobSpec(job_id, "tiny", "tiny", flow_name, "TT", 0, "ns")


class MixedAdapter:
    def __init__(self, delayed_fixture_dir: Path) -> None:
        self.events: list[dict[str, str | float | int]] = []
        self.lock = threading.Lock()
        self.arrivals = 0
        self.gate = threading.Barrier(CAPACITY)
        self.normal = self._adapter(FIXTURE_DIR, "normal.sdc", "run.tcl", 2)
        self.tight = self._adapter(FIXTURE_DIR, "tight.sdc", "run.tcl", 2)
        self.timeout = self._adapter(delayed_fixture_dir, "normal.sdc", "delayed.tcl", 0.05)

    def _adapter(self, fixture_dir: Path, sdc_name: str, script_name: str, timeout_seconds: float) -> OpenStaSubprocessAdapter:
        return OpenStaSubprocessAdapter(
            sta_path=STA_PATH,
            liberty_path=LIBERTY_PATH,
            fixture_dir=fixture_dir,
            sdc_name=sdc_name,
            script_name=script_name,
            timeout_seconds=timeout_seconds,
            process_observer=self._observe_start,
        )

    def _observe_start(self, pid: int, started_at: float) -> None:
        with self.lock:
            self.events.append({"kind": "process_started", "pid": pid, "at": started_at})

    def run(self, job_spec: JobSpec):
        with self.lock:
            self.arrivals += 1
            gated = self.arrivals <= CAPACITY
        if gated:
            self.gate.wait(timeout=2)
        adapter = {"normal": self.normal, "tight": self.tight, "timeout": self.timeout}[job_spec.flow_name]
        return adapter.run(job_spec)


class InterruptAfterArtifactAdapter:
    """Inject worker loss only after a real OpenSTA child has returned."""

    def __init__(self) -> None:
        self.completed_child = False
        self.delegate = OpenStaSubprocessAdapter(
            sta_path=STA_PATH,
            liberty_path=LIBERTY_PATH,
            fixture_dir=FIXTURE_DIR,
            timeout_seconds=2,
        )

    def run(self, job_spec: JobSpec):
        result = self.delegate.run(job_spec)
        self.completed_child = result.process_exit_code == 0
        raise SystemExit("injected worker loss after real artifact return")


def delayed_fixture() -> tempfile.TemporaryDirectory[str]:
    directory = tempfile.TemporaryDirectory(prefix="eda-opensta-load-timeout-")
    root = Path(directory.name)
    for name in ("tiny_mapped.v", "normal.sdc"):
        shutil.copy2(FIXTURE_DIR / name, root / name)
    (root / "delayed.tcl").write_text(
        "after 1000\n" + (FIXTURE_DIR / "run.tcl").read_text(encoding="utf-8"), encoding="utf-8"
    )
    return directory


def main() -> None:
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    with delayed_fixture() as directory_name:
        adapter = MixedAdapter(Path(directory_name))
        service = JobService(
            Store(), max_workers=CAPACITY, max_attempts=1, adapter=adapter,
            resource_slots=CAPACITY, max_in_flight=CAPACITY, worker_id="single-host-load-recovery",
        )
        batch = [spec(f"normal-{index}") for index in range(6)] + [spec("tight-0", "tight"), spec("timeout-0", "timeout")]
        for item in batch:
            service.submit(item)
        try:
            service.submit(spec("rejected-while-full"))
            rejected_reason = None
        except BackpressureError as exc:
            rejected_reason = str(exc)
        for item in batch:
            service.futures[item.job_id].result(timeout=5)
        initial_process_start_count = len(adapter.events)
        post_timeout = spec("post-timeout")
        service.submit(post_timeout)
        service.futures[post_timeout.job_id].result(timeout=5)
        mixed_states = {item.job_id: service.get(item.job_id) for item in (*batch, post_timeout)}

    interrupted_adapter = InterruptAfterArtifactAdapter()
    interrupted_service = JobService(
        Store(), max_workers=1, max_attempts=1, adapter=interrupted_adapter,
        resource_slots=1, max_in_flight=1, worker_id="single-host-recovery", lease_seconds=0.01,
    )
    interrupted = spec("worker-loss")
    interrupted_service.submit(interrupted)
    try:
        interrupted_service.futures[interrupted.job_id].result(timeout=5)
    except SystemExit:
        pass
    before_recovery = interrupted_service.get(interrupted.job_id)
    time.sleep(0.03)
    reconciliation = interrupted_service.recover_stale_runs(stale_after_seconds=0)
    after_recovery = interrupted_service.get(interrupted.job_id)
    starts = [event["at"] for event in adapter.events if event["kind"] == "process_started"]
    payload = {
        "synthetic": False,
        "scope": "single-host mixed OpenSTA load and worker-loss recovery",
        "profile": {"max_workers": CAPACITY, "max_in_flight": CAPACITY, "resource_slots": CAPACITY},
        "mixed_batch": {
            "states": {job_id: {"status": state["status"], "check_status": state["check_status"], "trust_status": state["trust_status"]}
                       for job_id, state in mixed_states.items()},
            "rejected_while_full": rejected_reason,
            "rejected_stored_run": service.get("rejected-while-full"),
            "first_batch_process_start_count": initial_process_start_count,
            "total_process_start_count_after_post_timeout": len(starts),
        },
        "worker_loss_recovery": {
            "real_child_completed": interrupted_adapter.completed_child,
            "before_recovery": {"status": before_recovery["status"], "attempt_status": before_recovery["attempts"][-1]["status"]},
            "reconciliation": reconciliation,
            "after_recovery": {"status": after_recovery["status"], "attempt_status": after_recovery["attempts"][-1]["status"], "error": after_recovery["error"]},
        },
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
