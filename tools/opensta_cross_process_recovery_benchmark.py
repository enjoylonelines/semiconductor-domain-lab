"""Measure whether single-host reconciliation can see a child after worker SIGKILL."""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from eda_lab.service import JobService
from eda_lab.store import Store


REPOSITORY_ROOT = Path(__file__).parents[1]
FIXTURE_DIR = REPOSITORY_ROOT / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")
WORKER = REPOSITORY_ROOT / "tools/opensta_external_worker.py"


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def wait_for(path: Path, timeout_seconds: float = 3) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not path.exists():
        if time.monotonic() >= deadline:
            raise TimeoutError(f"timed out waiting for {path}")
        time.sleep(0.01)


def wait_until_gone(pid: int, timeout_seconds: float = 3) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while alive(pid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)
    return True


def main() -> None:
    if not STA_PATH.is_file() or not LIBERTY_PATH.is_file():
        raise SystemExit("OpenSTA executable or Liberty fixture is unavailable")
    with tempfile.TemporaryDirectory(prefix="eda-cross-process-") as directory_name:
        root = Path(directory_name)
        fixture = root / "fixture"
        fixture.mkdir()
        for name in ("tiny_mapped.v", "normal.sdc"):
            shutil.copy2(FIXTURE_DIR / name, fixture / name)
        (fixture / "delayed.tcl").write_text(
            "after 1000\n" + (FIXTURE_DIR / "run.tcl").read_text(encoding="utf-8"), encoding="utf-8"
        )
        database = root / "runs.sqlite"
        child_pid_file = root / "opensta.pid"
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(REPOSITORY_ROOT / "src")
        worker = subprocess.Popen([
            sys.executable, str(WORKER), "--database", str(database), "--fixture-dir", str(fixture),
            "--sta-path", str(STA_PATH), "--liberty-path", str(LIBERTY_PATH), "--child-pid-file", str(child_pid_file),
        ], cwd=REPOSITORY_ROOT, env=environment, start_new_session=True)
        child_pid = None
        try:
            wait_for(child_pid_file)
            child_pid = int(child_pid_file.read_text(encoding="utf-8"))
            os.kill(worker.pid, signal.SIGKILL)
            worker.wait(timeout=2)
            child_alive_before_recovery = alive(child_pid)
            time.sleep(0.12)
            store = Store(database)
            service = JobService(store, max_workers=1, lease_seconds=0.05)
            before = service.get("cross-process-worker-loss")
            first_reconciliation = service.recover_stale_runs(stale_after_seconds=0)
            after_live_child_check = service.get("cross-process-worker-loss")
            child_alive_after_recovery = alive(child_pid)
            child_exited_before_second_reconciliation = wait_until_gone(child_pid)
            second_reconciliation = service.recover_stale_runs(stale_after_seconds=0)
            after_child_exit = service.get("cross-process-worker-loss")
            payload = {
                "synthetic": False,
                "scope": "worker SIGKILL while delayed real OpenSTA child is alive",
                "worker_exit_signal": "SIGKILL",
                "child_alive_before_recovery": child_alive_before_recovery,
                "child_alive_after_recovery": child_alive_after_recovery,
                "before_recovery": {"status": before["status"], "attempt_status": before["attempts"][-1]["status"]},
                "first_reconciliation": first_reconciliation,
                "after_live_child_check": {
                    "status": after_live_child_check["status"],
                    "attempt_status": after_live_child_check["attempts"][-1]["status"],
                },
                "child_exited_before_second_reconciliation": child_exited_before_second_reconciliation,
                "second_reconciliation": second_reconciliation,
                "after_child_exit": {
                    "status": after_child_exit["status"],
                    "attempt_status": after_child_exit["attempts"][-1]["status"],
                },
            }
            print(json.dumps(payload, sort_keys=True))
        finally:
            if worker.poll() is None:
                worker.kill()
                worker.wait(timeout=2)
            if child_pid is not None and alive(child_pid):
                os.killpg(child_pid, signal.SIGKILL)


if __name__ == "__main__":
    main()
