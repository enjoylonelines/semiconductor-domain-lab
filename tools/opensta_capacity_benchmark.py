"""Measure bounded OpenSTA concurrency on one explicitly described host.

This is a local capacity experiment, not a deployment-sizing recommendation.
It starts no more than eight fixed-fixture OpenSTA children at once and retains
the environment and aggregate child CPU/RSS measurements with each result.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import resource
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

from eda_lab.models import JobSpec
from eda_lab.runner import OpenStaSubprocessAdapter


REPOSITORY_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPOSITORY_ROOT / "docs/evidence/2026-09-24-real-sta"
DEFAULT_STA = Path("/tmp/eda-opensta-20260924/build/sta")
DEFAULT_LIBERTY = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")


def _sysctl(name: str) -> str | None:
    try:
        return subprocess.check_output(["sysctl", "-n", name], text=True).strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None


def host_snapshot() -> dict[str, object]:
    usage = shutil.disk_usage(REPOSITORY_ROOT)
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "logical_cpu_count": os.cpu_count(),
        "physical_cpu_count": _sysctl("hw.physicalcpu"),
        "memory_bytes": _sysctl("hw.memsize"),
        "repository_disk_free_bytes": usage.free,
        "server_count": 1,
    }


def run_one(
    index: int,
    sta_path: Path,
    liberty_path: Path,
    start_barrier: threading.Barrier,
    process_events: list[dict[str, float | int]],
    events_lock: threading.Lock,
) -> dict[str, object]:
    def observe(pid: int, started_at: float) -> None:
        with events_lock:
            process_events.append({"pid": pid, "started_at_monotonic": started_at})

    adapter = OpenStaSubprocessAdapter(
        sta_path=sta_path,
        liberty_path=liberty_path,
        fixture_dir=FIXTURE_DIR,
        timeout_seconds=2,
        process_observer=observe,
    )
    start_barrier.wait()
    started = time.perf_counter()
    result = adapter.run(JobSpec(
        job_id=f"capacity-{index}",
        design_id="tiny",
        ip_family="tiny",
        flow_name="opensta-fixed-fixture-v1",
        corner="TT",
        worst_slack=0,
        unit="ns",
    ))
    completed_at = time.monotonic()
    return {
        "duration_seconds": time.perf_counter() - started,
        "exit_code": result.process_exit_code,
        "report_bytes": result.artifact_path.stat().st_size,
        "completed_at_monotonic": completed_at,
    }


def measure_level(concurrency: int, repeats: int, sta_path: Path, liberty_path: Path) -> dict[str, object]:
    batches: list[dict[str, object]] = []
    for batch in range(repeats):
        before = resource.getrusage(resource.RUSAGE_CHILDREN)
        started = time.perf_counter()
        process_events: list[dict[str, float | int]] = []
        events_lock = threading.Lock()
        start_barrier = threading.Barrier(concurrency)
        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            futures = [executor.submit(run_one, index, sta_path, liberty_path, start_barrier, process_events, events_lock)
                       for index in range(concurrency)]
            jobs = [future.result() for future in futures]
        after = resource.getrusage(resource.RUSAGE_CHILDREN)
        wall_seconds = time.perf_counter() - started
        batches.append({
            "batch": batch + 1,
            "wall_seconds": wall_seconds,
            "throughput_runs_per_second": concurrency / wall_seconds,
            "child_user_cpu_seconds": after.ru_utime - before.ru_utime,
            "child_system_cpu_seconds": after.ru_stime - before.ru_stime,
            "child_max_rss": after.ru_maxrss,
            "process_start_events": sorted(process_events, key=lambda event: event["started_at_monotonic"]),
            "controlled_overlap_confirmed": (
                len(process_events) == concurrency
                and max(event["started_at_monotonic"] for event in process_events)
                < min(job["completed_at_monotonic"] for job in jobs)
            ),
            "runs": jobs,
        })
    sorted_walls = sorted(batch["wall_seconds"] for batch in batches)
    return {
        "concurrency": concurrency,
        "repeats": repeats,
        "batches": batches,
        "p50_wall_seconds": sorted_walls[len(sorted_walls) // 2],
        "p95_wall_seconds": sorted_walls[min(len(sorted_walls) - 1, int(len(sorted_walls) * 0.95))],
        "mean_throughput_runs_per_second": sum(batch["throughput_runs_per_second"] for batch in batches) / repeats,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 2, 4, 8])
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--sta-path", type=Path, default=DEFAULT_STA)
    parser.add_argument("--liberty-path", type=Path, default=DEFAULT_LIBERTY)
    args = parser.parse_args()
    if not args.sta_path.is_file() or not args.liberty_path.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    if args.repeats < 1 or any(level < 1 or level > 8 for level in args.concurrency):
        raise SystemExit("repeats must be positive and concurrency must be between 1 and 8")

    payload = {
        "synthetic": False,
        "scope": "single-host fixed OpenSTA fixture capacity experiment",
        "guardrails": {
            "maximum_concurrency": 8,
            "child_timeout_seconds": 2,
            "server_count": 1,
            "no_license_capacity_claim": True,
        },
        "host": host_snapshot(),
        "sta_path": str(args.sta_path),
        "liberty_path": str(args.liberty_path),
        "fixture_dir": str(FIXTURE_DIR),
        "levels": [measure_level(level, args.repeats, args.sta_path, args.liberty_path) for level in args.concurrency],
    }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
