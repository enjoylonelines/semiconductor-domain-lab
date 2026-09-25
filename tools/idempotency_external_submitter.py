"""One disposable process for the cross-process idempotency experiment."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from eda_lab.models import JobSpec
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import BackpressureError, JobService
from eda_lab.store import Store


def wait_for(path: Path, timeout_seconds: float = 3) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for {path}")
        time.sleep(0.01)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--sta-path", required=True, type=Path)
    parser.add_argument("--liberty-path", required=True, type=Path)
    parser.add_argument("--release-file", required=True, type=Path)
    parser.add_argument("--ready-file", required=True, type=Path)
    parser.add_argument("--result-file", required=True, type=Path)
    parser.add_argument("--child-pids", required=True, type=Path)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--job-id", default="cross-process-idempotency")
    parser.add_argument("--max-in-flight", type=int)
    args = parser.parse_args()

    def observe(pid: int, _started_at: float) -> None:
        with args.child_pids.open("a", encoding="utf-8") as output:
            output.write(f"{pid}\n")

    adapter = OpenStaSubprocessAdapter(
        sta_path=args.sta_path, liberty_path=args.liberty_path, fixture_dir=args.fixture_dir,
        process_observer=observe,
    )
    service = JobService(
        Store(args.database), max_workers=1, max_attempts=1, adapter=adapter, worker_id=args.worker_id,
        max_in_flight=args.max_in_flight,
    )
    spec = JobSpec(args.job_id, "tiny", "tiny", "normal", "TT", 0, "ns")
    args.ready_file.write_text("ready", encoding="utf-8")
    wait_for(args.release_file)
    try:
        result = service.submit(spec)
    except BackpressureError as exc:
        args.result_file.write_text(json.dumps({"scheduled": False, "rejected": True, "reason": str(exc)}, sort_keys=True), encoding="utf-8")
        return
    future = service.futures.get(spec.job_id)
    if future is not None:
        future.result(timeout=10)
    final = service.get(spec.job_id)
    args.result_file.write_text(json.dumps({
        "scheduled": future is not None,
        "rejected": False,
        "returned_status": result["status"],
        "final_status": final["status"],
    }, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
