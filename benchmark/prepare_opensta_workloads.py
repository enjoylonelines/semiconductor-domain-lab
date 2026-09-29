#!/usr/bin/env python3
"""Prepare pinned external OpenSTA calibration fixtures under /tmp."""
from pathlib import Path
import shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]
PICO_DIR = Path("/tmp/eda-picorv32-workload")
PICO_REV = "ef203c2b0a3fb793280f5114941416c425c5b461"
OPENSTA = Path("/tmp/eda-opensta-20260924")
LIB = OPENSTA / "examples/sky130hd_tt.lib"

def run(cmd):
    print("+", " ".join(map(str, cmd)))
    subprocess.run(list(map(str, cmd)), check=True, cwd=ROOT)

if not (OPENSTA / "build/sta").exists() or not LIB.exists():
    raise SystemExit("Pinned OpenSTA build/Liberty missing; restore the repo's documented OpenSTA 3.1.0 setup first.")

if not PICO_DIR.exists():
    run(["git", "clone", "https://github.com/YosysHQ/picorv32.git", str(PICO_DIR)])
run(["git", "-C", str(PICO_DIR), "checkout", "--detach", PICO_REV])

pico = PICO_DIR / "picorv32.v"
common = (
    f"read_verilog {pico}; "
    "hierarchy -top {top}; synth -top {top}; "
    f"dfflibmap -liberty {LIB}; abc -liberty {LIB}; clean; "
    "write_verilog -noattr {out}"
)
run(["yosys", "-Q", "-p", common.format(top="picorv32", out="/tmp/picorv32_sky130hd.v")])
run(["yosys", "-Q", "-p",
     f"read_verilog {pico} {ROOT/'benchmark/picorv32_bench_top.v'}; "
     "hierarchy -top picorv32_bench_top; synth -top picorv32_bench_top; "
     f"dfflibmap -liberty {LIB}; abc -liberty {LIB}; clean; "
     "write_verilog -noattr /tmp/picorv32x16_sky130hd.v"])
print("Prepared Medium and Heavy mapped netlists. No Cycle 1 code was invoked.")
