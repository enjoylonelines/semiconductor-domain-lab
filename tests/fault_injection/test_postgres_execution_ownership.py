"""Actual OpenSTA fault injection for PostgreSQL execution ownership.

These tests require a disposable PostgreSQL database and the recorded local
OpenSTA fixture. They intentionally use separate worker processes: a thread
cannot reproduce the loss of worker-local process ownership.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import JobService
from eda_lab.worker import PostgresWorker


DSN = os.environ.get("EDA_POSTGRES_TEST_DSN")
ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = ROOT / "docs/evidence/2026-09-24-real-sta"
STA_PATH = Path("/tmp/eda-opensta-20260924/build/sta")
LIBERTY_PATH = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")


def wait_until(predicate, *, timeout: float = 3.0, message: str) -> object:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(message)


@unittest.skipUnless(DSN, "set EDA_POSTGRES_TEST_DSN for a dedicated disposable PostgreSQL database")
@unittest.skipUnless(STA_PATH.is_file() and LIBERTY_PATH.is_file(), "OpenSTA integration fixture is unavailable")
class PostgresExecutionOwnershipFaultTests(unittest.TestCase):
    def setUp(self):
        self.prefix = uuid4().hex
        self.store = PostgresStore(DSN)
        self.job_ids: list[str] = []
        self.processes: list[subprocess.Popen] = []
        self.tempdirs: list[tempfile.TemporaryDirectory] = []

    def tearDown(self):
        for process in self.processes:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)
        for directory in self.tempdirs:
            directory.cleanup()
        for job_id in self.job_ids:
            run = self.store.get_run(job_id)
            if run is None or run["status"] not in {"QUEUED", "RUNNING"}:
                continue
            if run["attempts"] and run["attempts"][-1]["status"] == "RUNNING":
                attempt = run["attempts"][-1]
                self.store.record_attempt(
                    job_id, attempt["attempt_no"], "ABANDONED",
                    error_type="test_cleanup", error="fault-test cleanup after a non-terminal assertion",
                    retry_class="test_cleanup",
                )
            self.store.update_run(job_id, status="FAILED", error="fault-test cleanup after a non-terminal assertion")
        self.store.close()

    def spec(self, suffix: str) -> JobSpec:
        return JobSpec(f"{self.prefix}-{suffix}", "d", "ip", "timing", "TT", 0.1, "ns")

    def delayed_fixture(self, delay_ms: int = 1000) -> Path:
        directory = tempfile.TemporaryDirectory(prefix="eda-postgres-fault-")
        self.tempdirs.append(directory)
        copied = Path(directory.name)
        for name in ("tiny_mapped.v", "normal.sdc"):
            (copied / name).write_bytes((FIXTURE_DIR / name).read_bytes())
        (copied / "delayed.tcl").write_text(
            f"after {delay_ms}\n" + (FIXTURE_DIR / "run.tcl").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        return copied

    def submit(self, spec: JobSpec) -> None:
        self.job_ids.append(spec.job_id)
        service = JobService(self.store, max_workers=1, max_attempts=1, worker_id="api", max_in_flight=8,
                             execution_mode="external")
        self.addCleanup(service.close)
        self.assertEqual(service.submit(spec)["status"], "QUEUED")

    def worker_process(self, fixture_dir: Path, *, kill_at_completion: bool = False) -> subprocess.Popen:
        adapter_definition = "" if not kill_at_completion else '''class KillAtCompletionAdapter(OpenStaSubprocessAdapter):
    def run(self, spec):
        result = super().run(spec)
        os.kill(os.getpid(), signal.SIGKILL)
        return result
'''
        script = f'''import os, signal
from pathlib import Path
from eda_lab.postgres_store import PostgresStore
from eda_lab.runner import OpenStaSubprocessAdapter
from eda_lab.service import JobService
from eda_lab.worker import PostgresWorker
{adapter_definition}
store = PostgresStore(os.environ["EDA_POSTGRES_TEST_DSN"])
adapter = {"KillAtCompletionAdapter" if kill_at_completion else "OpenStaSubprocessAdapter"}(sta_path=Path({str(STA_PATH)!r}), liberty_path=Path({str(LIBERTY_PATH)!r}), fixture_dir=Path({str(fixture_dir)!r}), script_name="delayed.tcl", timeout_seconds=5)
service = JobService(store, max_workers=1, max_attempts=1, adapter=adapter, worker_id="fault-worker", lease_seconds=0.10, max_in_flight=8, execution_mode="external")
try:
    PostgresWorker(store, service).drain()
finally:
    service.close()
'''
        environment = os.environ.copy()
        source_path = str(ROOT / "src")
        environment["PYTHONPATH"] = source_path + (os.pathsep + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
        process = subprocess.Popen([sys.executable, "-c", script], env=environment)
        self.processes.append(process)
        return process

    def expired(self, job_id: str) -> bool:
        run = self.store.get_run(job_id)
        return bool(run and run["attempts"] and run["attempts"][-1]["lease_expires_at"] < time.time())

    def reconcile(self):
        service = JobService(self.store, max_workers=1, max_attempts=1, worker_id="reconciler", execution_mode="external")
        self.addCleanup(service.close)
        return service.recover_stale_runs(stale_after_seconds=0)

    def test_worker_loss_with_live_child_blocks_new_attempt_until_child_death(self):
        spec = self.spec("live-child")
        self.submit(spec)
        worker = self.worker_process(self.delayed_fixture())
        attempt = wait_until(
            lambda: self._latest_attempt_with_pid(spec.job_id),
            message="worker did not record an OpenSTA attempt",
        )
        child_pid = attempt["process_pid"]
        self.assertIsNotNone(child_pid)
        os.kill(worker.pid, signal.SIGKILL)
        self.assertEqual(worker.wait(timeout=2), -signal.SIGKILL)
        wait_until(lambda: self.expired(spec.job_id), message="worker lease did not expire")

        outcome = self.reconcile()
        running = self.store.get_run(spec.job_id)
        self.assertEqual(outcome["skipped_live_child"], [spec.job_id])
        self.assertEqual(running["status"], "RUNNING")
        self.assertEqual([(a["attempt_no"], a["status"]) for a in running["attempts"]], [(1, "RUNNING")])

        # B2 uses a positively confirmed child death before abandonment; it never
        # treats lease expiry alone as permission to create attempt #2.
        os.kill(child_pid, signal.SIGTERM)
        wait_until(lambda: not self._pid_exists(child_pid), message="OpenSTA child remained alive after SIGTERM")
        outcome = self.reconcile()
        recovered = self.store.get_run(spec.job_id)
        self.assertEqual(outcome["recovered"], [spec.job_id])
        self.assertEqual(recovered["status"], "FAILED")
        self.assertEqual([(a["attempt_no"], a["status"]) for a in recovered["attempts"]], [(1, "ABANDONED")])

    def test_completion_boundary_kill_cannot_accept_partial_completion(self):
        spec = self.spec("completion-boundary")
        self.submit(spec)
        worker = self.worker_process(self.delayed_fixture(delay_ms=50), kill_at_completion=True)
        self.assertEqual(worker.wait(timeout=3), -signal.SIGKILL)
        wait_until(lambda: self.expired(spec.job_id), message="completion-boundary lease did not expire")

        outcome = self.reconcile()
        recovered = self.store.get_run(spec.job_id)
        self.assertEqual(outcome["recovered"], [spec.job_id])
        self.assertEqual(recovered["status"], "FAILED")
        self.assertNotEqual(recovered["status"], "SUCCEEDED")
        self.assertEqual([(a["attempt_no"], a["status"]) for a in recovered["attempts"]], [(1, "ABANDONED")])
        self.assertIsNone(recovered["metrics"])

    @staticmethod
    def _pid_exists(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def _latest_attempt(self, job_id: str):
        run = self.store.get_run(job_id)
        return run["attempts"][-1] if run and run["attempts"] else None

    def _latest_attempt_with_pid(self, job_id: str):
        attempt = self._latest_attempt(job_id)
        return attempt if attempt and attempt["process_pid"] is not None else None


if __name__ == "__main__":
    unittest.main()
