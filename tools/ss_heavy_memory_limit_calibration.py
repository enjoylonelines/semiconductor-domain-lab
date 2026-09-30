"""Measure the minimum cgroup memory limit for one SS Heavy OpenSTA child."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STAGE = Path("/Users/hb/Documents/Codex/phase5-workload")
IMAGE = "eda-multihost-m1-host-agent-a"


def read_int(path: Path) -> int | None:
    try:
        return int(path.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limits-gib", type=float, nargs="+", default=[1.25, 1.5, 2.0])
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--stage", type=Path, default=DEFAULT_STAGE)
    parser.add_argument("--raw-dir", type=Path, default=ROOT / "benchmark/raw/ss-memory-limit-f2e289")
    args = parser.parse_args()
    if args.repeats < 1 or any(limit <= 0 for limit in args.limits_gib):
        raise SystemExit("limits and repeats must be positive")
    required = (args.stage / "sky130_fd_sc_hd__ss_100C_1v60.lib", args.stage / "picorv32x64_sky130hd.v")
    if not all(path.is_file() for path in required):
        raise SystemExit("stage must contain the SS Liberty and Heavy netlist")

    rows = []
    for limit in args.limits_gib:
        for repeat in range(1, args.repeats + 1):
            name = f"ss-memory-{str(limit).replace('.', '-')}-{repeat}"
            destination = args.raw_dir / f"{limit:g}GiB" / f"run-{repeat:02d}"
            destination.mkdir(parents=True, exist_ok=True)
            bytes_limit = int(limit * 1024 ** 3)
            command = [
                "docker", "run", "--name", name, "--memory", str(bytes_limit), "--memory-swap", str(bytes_limit),
                "--cpus", "1", "-v", f"{args.stage}:/phase5:ro", IMAGE, "sh", "-c",
                "mkdir -p /results; /opt/opensta/build/sta -no_init -exit "
                "/app/docs/evidence/2026-09-24-real-sta/picorv32x64_calibration.tcl "
                ">/results/stdout.log 2>/results/stderr.log; rc=$?; echo $rc >/results/exit_code; "
                "cat /sys/fs/cgroup/memory.events >/results/memory.events; "
                "cat /sys/fs/cgroup/memory.peak >/results/memory.peak; exit 0",
            ]
            environment = {
                "EDA_LIB": "/phase5/sky130_fd_sc_hd__ss_100C_1v60.lib",
                "EDA_NETLIST": "/phase5/picorv32x64_sky130hd.v",
            }
            command[2:2] = [item for pair in (("-e", f"{key}={value}") for key, value in environment.items()) for item in pair]
            started = time.perf_counter()
            process = subprocess.run(command, text=True, capture_output=True, check=False)
            wall_seconds = time.perf_counter() - started
            subprocess.run(["docker", "cp", f"{name}:/results/.", str(destination)], check=True)
            subprocess.run(["docker", "rm", name], check=True, capture_output=True)
            exit_code = read_int(destination / "exit_code")
            events = {}
            for line in (destination / "memory.events").read_text().splitlines():
                key, value = line.split()
                events[key] = int(value)
            stdout = (destination / "stdout.log").read_text(errors="replace")
            rows.append({
                "limit_gib": limit,
                "repeat": repeat,
                "docker_returncode": process.returncode,
                "opensta_exit_code": exit_code,
                "wall_seconds": wall_seconds,
                "memory_peak_bytes": read_int(destination / "memory.peak"),
                "oom_kill": events.get("oom_kill", 0),
                "valid_report": exit_code == 0 and "EDA_LAB_REPORT_END" in stdout,
                "raw_dir": str(destination.resolve().relative_to(ROOT)),
            })
    output = {"scope": "one SS Heavy child per bounded Docker container", "runs": rows}
    (args.raw_dir / "summary.json").write_text(json.dumps(output, indent=2) + "\n")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
