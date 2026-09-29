#!/usr/bin/env python3
"""Reproducible OpenSTA workload calibration/scaling harness.

Calibration is safe during Cycle 1. Scaling/fault execution is intentionally
not wired to Cycle 1 ownership/recovery code.
"""
from __future__ import annotations
import argparse, hashlib, json, os, platform, re, statistics, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STA = Path("/tmp/eda-opensta-20260924/build/sta")
WORKLOADS = {
    "small": ROOT / "benchmark/small_calibration.tcl",
    "medium": ROOT / "benchmark/picorv32_calibration.tcl",
    "heavy": ROOT / "benchmark/picorv32x64_calibration.tcl",
}

def percentile(values, q):
    xs = sorted(values)
    pos = (len(xs)-1)*q
    lo, hi = int(pos), min(int(pos)+1, len(xs)-1)
    frac = pos-lo
    return xs[lo]*(1-frac)+xs[hi]*frac

def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_once(sta: Path, script: Path, raw_dir: Path, name: str, idx: int, environment: dict[str, str]):
    raw_dir.mkdir(parents=True, exist_ok=True)
    out = raw_dir / f"{name}-{idx:02d}.stdout.log"
    err = raw_dir / f"{name}-{idx:02d}.stderr.log"
    before = time.perf_counter()
    with out.open("wb") as stdout, err.open("wb") as stderr:
        proc = subprocess.run(
            ["/usr/bin/time", "-l", str(sta), "-no_init", "-exit", str(script)],
            cwd=ROOT, stdout=stdout, stderr=stderr, env=environment, check=False,
        )
    wall = time.perf_counter() - before
    stderr_text = err.read_text(errors="replace")
    m_user = re.search(r"([0-9.]+) real\s+([0-9.]+) user\s+([0-9.]+) sys", stderr_text)
    m_rss = re.search(r"(\d+)\s+maximum resident set size", stderr_text)
    stdout_text = out.read_text(errors="replace")
    valid = proc.returncode == 0 and "Error:" not in stdout_text
    return {
        "run": idx, "returncode": proc.returncode, "valid": valid,
        "wall_clock_s_external": wall,
        "time_real_s": float(m_user.group(1)) if m_user else None,
        "cpu_user_s": float(m_user.group(2)) if m_user else None,
        "cpu_sys_s": float(m_user.group(3)) if m_user else None,
        "peak_rss_bytes": int(m_rss.group(1)) if m_rss else None,
        "report_bytes": out.stat().st_size,
        "stdout": display_path(out), "stderr": display_path(err),
    }

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--workload", choices=[*WORKLOADS, "all"], default="all")
    p.add_argument("--repeats", type=int, default=5)
    p.add_argument("--sta", type=Path, default=DEFAULT_STA)
    p.add_argument("--liberty", type=Path)
    p.add_argument("--netlist", type=Path)
    p.add_argument("--raw-dir", type=Path, default=ROOT/"benchmark/raw")
    p.add_argument("--output", type=Path, default=ROOT/"benchmark/raw/calibration-summary.json")
    args = p.parse_args()
    names = list(WORKLOADS) if args.workload == "all" else [args.workload]
    environment = os.environ.copy()
    if args.liberty:
        environment["EDA_LIB"] = str(args.liberty)
    if args.netlist:
        environment["EDA_NETLIST"] = str(args.netlist)
    payload = {"environment": {
        "platform": platform.platform(), "machine": platform.machine(),
        "sta": str(args.sta), "python": platform.python_version(),
        "liberty": str(args.liberty) if args.liberty else environment.get("EDA_LIB"),
        "liberty_sha256": sha256(args.liberty) if args.liberty else None,
        "netlist": str(args.netlist) if args.netlist else environment.get("EDA_NETLIST"),
        "netlist_sha256": sha256(args.netlist) if args.netlist else None,
    }, "workloads": {}}
    for name in names:
        runs = [run_once(args.sta, WORKLOADS[name], args.raw_dir, name, i+1, environment)
                for i in range(args.repeats)]
        valid = [r for r in runs if r["valid"]]
        vals = [r["time_real_s"] for r in valid if r["time_real_s"] is not None]
        payload["workloads"][name] = {
            "runs": runs, "valid_runs": len(valid),
            "median_real_s": statistics.median(vals) if vals else None,
            "p95_real_s": percentile(vals, .95) if vals else None,
            "peak_rss_bytes_max": max((r["peak_rss_bytes"] for r in valid), default=None),
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2)+"\n")
    print(json.dumps(payload, indent=2))

if __name__ == "__main__":
    main()
