"""One disposable worker process for cross-process OpenSTA recovery experiments."""

from __future__ import annotations

import argparse
from pathlib import Path

from eda_lab.models import JobSpec
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import JobService
from eda_lab.store import Store


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--fixture-dir", required=True, type=Path)
    parser.add_argument("--sta-path", required=True, type=Path)
    parser.add_argument("--liberty-path", required=True, type=Path)
    parser.add_argument("--child-pid-file", required=True, type=Path)
    args = parser.parse_args()

    def observe(pid: int, _started_at: float) -> None:
        args.child_pid_file.write_text(str(pid), encoding="utf-8")

    adapter = OpenStaSubprocessAdapter(
        sta_path=args.sta_path, liberty_path=args.liberty_path, fixture_dir=args.fixture_dir,
        script_name="delayed.tcl", timeout_seconds=5, process_observer=observe,
    )
    service = JobService(
        Store(args.database), max_workers=1, max_attempts=1, adapter=adapter,
        resource_slots=1, max_in_flight=1, worker_id="external-worker", lease_seconds=0.05,
    )
    job = JobSpec("cross-process-worker-loss", "tiny", "tiny", "normal", "TT", 0, "ns")
    service.submit(job)
    service.futures[job.job_id].result(timeout=10)


if __name__ == "__main__":
    main()
