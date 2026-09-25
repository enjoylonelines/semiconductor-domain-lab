"""Measure independent SQLite submitters for distinct real OpenSTA workloads."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from eda_lab.store import Store


REPOSITORY_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPOSITORY_ROOT / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")
SUBMITTER = REPOSITORY_ROOT / "tools/idempotency_external_submitter.py"
CONTENDERS = 8


def wait_for(paths: list[Path], timeout_seconds: float = 3) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not all(path.exists() for path in paths):
        if time.monotonic() >= deadline:
            raise TimeoutError("timed out waiting for submitters")
        time.sleep(0.01)


def main() -> None:
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    with tempfile.TemporaryDirectory(prefix="eda-cross-submit-") as directory_name:
        root = Path(directory_name)
        database = root / "runs.sqlite"
        Store(database)
        release_file = root / "release"
        child_pids = root / "opensta-pids"
        environment = {**os.environ, "PYTHONPATH": str(REPOSITORY_ROOT / "src")}
        processes = []
        result_files = []
        started_at = time.monotonic()
        try:
            for index in range(CONTENDERS):
                ready_file = root / f"ready-{index}"
                result_file = root / f"result-{index}.json"
                process = subprocess.Popen([
                    sys.executable, str(SUBMITTER), "--database", str(database), "--fixture-dir", str(FIXTURE_DIR),
                    "--sta-path", str(STA_PATH), "--liberty-path", str(LIBERTY_PATH),
                    "--release-file", str(release_file), "--ready-file", str(ready_file), "--result-file", str(result_file),
                    "--child-pids", str(child_pids), "--worker-id", f"contender-{index}", "--job-id", f"cross-submit-{index}",
                ], cwd=REPOSITORY_ROOT, env=environment)
                processes.append(process)
                result_files.append(result_file)
            wait_for([root / f"ready-{index}" for index in range(CONTENDERS)])
            release_file.write_text("go", encoding="utf-8")
            for process in processes:
                if process.wait(timeout=15) != 0:
                    raise RuntimeError(f"submitter exited with {process.returncode}")
            wait_for(result_files)
            results = [json.loads(path.read_text(encoding="utf-8")) for path in result_files]
            runs = [Store(database).get_run(f"cross-submit-{index}")["status"] for index in range(CONTENDERS)]
            print(json.dumps({
                "synthetic": False,
                "scope": f"{CONTENDERS} external submitters with distinct job_id values released concurrently",
                "contenders": CONTENDERS,
                "observed_opensta_children": len(child_pids.read_text(encoding="utf-8").splitlines()) if child_pids.exists() else 0,
                "scheduled": sum(result["scheduled"] for result in results),
                "succeeded": sum(status == "SUCCEEDED" for status in runs),
                "wall_seconds": round(time.monotonic() - started_at, 6),
            }, sort_keys=True))
        finally:
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)


if __name__ == "__main__":
    main()
