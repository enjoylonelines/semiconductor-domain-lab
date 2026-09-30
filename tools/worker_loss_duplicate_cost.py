"""Measure avoidable duplicate OpenSTA compute after a worker-loss decision boundary.

This is a bounded A/B policy benchmark. The "naive" mode intentionally launches
the same SS Heavy analysis again while the first OpenSTA process is still alive.
The "fenced" mode keeps the original execution only.
"""

from __future__ import annotations

import argparse
import json
import os
import resource
import subprocess
import time
from pathlib import Path


def wait_with_rusage(process: subprocess.Popen) -> tuple[int, float, float, float]:
    begun = time.perf_counter()
    pid, status, usage = os.wait4(process.pid, 0)
    if pid != process.pid:
        raise RuntimeError("wait4 returned an unexpected child")
    ended = time.perf_counter()
    return os.waitstatus_to_exitcode(status), usage.ru_utime, usage.ru_stime, ended


def launch(sta_path: Path, script_path: Path, env: dict[str, str]) -> tuple[subprocess.Popen, float]:
    started = time.perf_counter()
    process = subprocess.Popen(
        [str(sta_path), str(script_path)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return process, started


def run_once(args, mode: str) -> dict:
    env = os.environ.copy()
    env["EDA_LIB"] = str(args.liberty)
    env["EDA_NETLIST"] = str(args.netlist)

    primary, primary_started = launch(args.sta, args.script, env)
    time.sleep(args.fault_after_seconds)
    if primary.poll() is not None:
        raise RuntimeError("primary OpenSTA exited before the fault boundary")

    fault_at = time.perf_counter()
    duplicate = None
    duplicate_started = None
    if mode == "naive":
        duplicate, duplicate_started = launch(args.sta, args.script, env)

    primary_rc, primary_user, primary_sys, primary_ended = wait_with_rusage(primary)
    if primary_rc != 0:
        raise RuntimeError(f"primary OpenSTA exited {primary_rc}")

    duplicate_payload = None
    if duplicate is not None:
        duplicate_rc, duplicate_user, duplicate_sys, duplicate_ended = wait_with_rusage(duplicate)
        if duplicate_rc != 0:
            raise RuntimeError(f"duplicate OpenSTA exited {duplicate_rc}")
        overlap = max(
            0.0,
            min(primary_ended, duplicate_ended) - max(primary_started, duplicate_started),
        )
        duplicate_payload = {
            "wall_seconds": duplicate_ended - duplicate_started,
            "user_cpu_seconds": duplicate_user,
            "system_cpu_seconds": duplicate_sys,
            "cpu_seconds": duplicate_user + duplicate_sys,
            "overlap_seconds": overlap,
        }

    primary_cpu = primary_user + primary_sys
    return {
        "mode": mode,
        "fault_after_seconds": args.fault_after_seconds,
        "primary": {
            "wall_seconds": primary_ended - primary_started,
            "user_cpu_seconds": primary_user,
            "system_cpu_seconds": primary_sys,
            "cpu_seconds": primary_cpu,
            "remaining_wall_after_fault_seconds": primary_ended - fault_at,
        },
        "duplicate": duplicate_payload,
        "total_child_cpu_seconds": primary_cpu + (duplicate_payload["cpu_seconds"] if duplicate_payload else 0.0),
    }


def median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle]


def summarize(samples: list[dict], mode: str) -> dict:
    result = {
        "mode": mode,
        "valid_repeats": len(samples),
        "primary_wall_seconds_median": median([s["primary"]["wall_seconds"] for s in samples]),
        "primary_cpu_seconds_median": median([s["primary"]["cpu_seconds"] for s in samples]),
        "remaining_wall_after_fault_seconds_median": median(
            [s["primary"]["remaining_wall_after_fault_seconds"] for s in samples]
        ),
        "total_child_cpu_seconds_median": median([s["total_child_cpu_seconds"] for s in samples]),
    }
    if mode == "naive":
        result.update({
            "duplicate_cpu_seconds_median": median([s["duplicate"]["cpu_seconds"] for s in samples]),
            "duplicate_wall_seconds_median": median([s["duplicate"]["wall_seconds"] for s in samples]),
            "overlap_seconds_median": median([s["duplicate"]["overlap_seconds"] for s in samples]),
        })
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sta", type=Path, required=True)
    parser.add_argument("--liberty", type=Path, required=True)
    parser.add_argument("--netlist", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--fault-after-seconds", type=float, default=0.5)
    parser.add_argument("--mode", choices=("fenced", "naive", "both"), default="both")
    args = parser.parse_args()

    for path in (args.sta, args.liberty, args.netlist, args.script):
        if not path.is_file():
            raise SystemExit(f"missing benchmark input: {path}")

    selected_modes = ("fenced", "naive") if args.mode == "both" else (args.mode,)
    all_samples = {}
    for mode in selected_modes:
        samples = [run_once(args, mode) for _ in range(args.repeats)]
        all_samples[mode] = samples

    payload = {
        "scope": "actual SS Heavy OpenSTA; counterfactual immediate-retry challenger vs current keep-original policy",
        "repeats_per_mode": args.repeats,
        "fault_after_seconds": args.fault_after_seconds,
        "summaries": {
            mode: summarize(samples, mode)
            for mode, samples in all_samples.items()
        },
        "samples": all_samples,
    }
    if set(selected_modes) == {"fenced", "naive"}:
        fenced_cpu = payload["summaries"]["fenced"]["total_child_cpu_seconds_median"]
        naive_cpu = payload["summaries"]["naive"]["total_child_cpu_seconds_median"]
        payload["derived"] = {
            "additional_child_cpu_seconds_per_fault_median": naive_cpu - fenced_cpu,
            "total_child_cpu_increase_percent": (naive_cpu / fenced_cpu - 1.0) * 100.0,
            "duplicate_overlap_seconds_per_fault_median": payload["summaries"]["naive"]["overlap_seconds_median"],
        }
    print(json.dumps(payload, sort_keys=True))


if __name__ == "__main__":
    main()
