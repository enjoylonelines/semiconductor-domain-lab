import threading
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from eda_lab.models import AdapterRunResult, JobSpec
from eda_lab.runner import OpenStaSubprocessAdapter, SyntheticTimingAdapter
from eda_lab.service import JobService
from eda_lab.store import Store


def spec(job_id: str) -> JobSpec:
    return JobSpec(job_id, "design-a", "PCIe", "synthetic-timing", "TT_25C", 0.12, "ns", duration_seconds=0)


class SequenceAdapter:
    def __init__(self):
        self.calls = 0
        self.success = SyntheticTimingAdapter()

    def run(self, job_spec):
        self.calls += 1
        if self.calls == 1:
            raise TimeoutError("injected retryable timeout")
        return self.success.run(job_spec)


class BlockingAdapter:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.success = SyntheticTimingAdapter()

    def run(self, job_spec):
        self.started.set()
        self.release.wait(timeout=2)
        return self.success.run(job_spec)


class AsyncLifecycleTests(unittest.TestCase):
    def test_attempt_lease_uses_a_token_and_heartbeat_cannot_be_stolen(self):
        clock = [100.0]
        store = Store(now=lambda: clock[0])
        store.create_run("leased", "design-a", "PCIe", "synthetic-timing")
        store.record_attempt("leased", 1, "RUNNING", retry_class="not_classified")

        self.assertTrue(store.acquire_attempt_lease("leased", 1, "worker-a", "token-a", 10))
        self.assertFalse(store.heartbeat_attempt("leased", 1, "token-b", 10))
        clock[0] = 105.0
        self.assertTrue(store.heartbeat_attempt("leased", 1, "token-a", 10))
        attempt = store.get_run("leased")["attempts"][-1]
        self.assertEqual(attempt["lease_owner"], "worker-a")
        self.assertEqual(attempt["lease_token"], "token-a")
        self.assertEqual(attempt["heartbeat_at"], 105.0)
        self.assertEqual(attempt["lease_expires_at"], 115.0)

    def test_expired_lease_is_a_reconciliation_candidate_not_success(self):
        clock = [100.0]
        store = Store(now=lambda: clock[0])
        store.create_run("expired-lease", "design-a", "PCIe", "synthetic-timing")
        store.record_attempt("expired-lease", 1, "RUNNING", retry_class="not_classified")
        store.acquire_attempt_lease("expired-lease", 1, "worker-a", "token-a", 1)
        clock[0] = 102.0

        self.assertEqual(store.list_expired_leased_attempts(clock[0]), [("expired-lease", 1)])
    def test_retryable_timeout_keeps_numbered_history_then_succeeds(self):
        service = JobService(Store(), max_workers=1, max_attempts=2, retry_delay_seconds=0, adapter=SequenceAdapter())
        service.submit(spec("retry-then-success"))
        service.futures["retry-then-success"].result(timeout=2)

        result = service.get("retry-then-success")
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual([(item["attempt_no"], item["status"], item["retry_class"]) for item in result["attempts"]], [
            (1, "RETRYABLE_FAILURE", "retryable"),
            (2, "SUCCEEDED", "not_applicable"),
        ])
        self.assertTrue(all(item["lease_token"] for item in result["attempts"]))

    def test_non_retryable_tool_exit_stops_at_first_attempt(self):
        successful = SyntheticTimingAdapter()

        class ToolExitAdapter:
            def run(self, job_spec):
                return AdapterRunResult(successful.run(job_spec).artifact_path, process_exit_code=9)

        service = JobService(Store(), max_workers=1, max_attempts=2, retry_delay_seconds=0, adapter=ToolExitAdapter())
        service.submit(spec("tool-exit-no-retry"))
        service.futures["tool-exit-no-retry"].result(timeout=2)
        result = service.get("tool-exit-no-retry")
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual([(item["attempt_no"], item["status"], item["retry_class"]) for item in result["attempts"]], [
            (1, "FAILED", "non_retryable"),
        ])

    def test_post_artifact_worker_interruption_is_recoverable_without_success(self):
        clock = [100.0]
        service = JobService(Store(now=lambda: clock[0]), max_workers=1, max_attempts=1)
        with patch("eda_lab.service.parse_report", side_effect=SystemExit("injected after artifact return")):
            service.submit(spec("post-artifact-interruption"))
            with self.assertRaises(SystemExit):
                service.futures["post-artifact-interruption"].result(timeout=2)

        interrupted = service.get("post-artifact-interruption")
        self.assertEqual(interrupted["status"], "RUNNING")
        self.assertEqual([(item["status"], item["retry_class"]) for item in interrupted["attempts"]], [
            ("RUNNING", "not_classified"),
        ])

        clock[0] = 101.0
        outcome = service.recover_stale_runs(stale_after_seconds=0)
        recovered = service.get("post-artifact-interruption")
        self.assertEqual(outcome, {"recovered": ["post-artifact-interruption"], "skipped_live": []})
        self.assertEqual(recovered["status"], "FAILED")
        self.assertNotEqual(recovered["status"], "SUCCEEDED")
        self.assertEqual(recovered["attempts"][-1]["status"], "ABANDONED")
        self.assertEqual(recovered["attempts"][-1]["error_type"], "worker_unavailable")
        self.assertEqual(recovered["attempts"][-1]["retry_class"], "recovery_required")

    def test_stale_database_record_is_not_recovered_while_worker_is_live(self):
        clock = [100.0]
        adapter = BlockingAdapter()
        service = JobService(Store(now=lambda: clock[0]), max_workers=1, max_attempts=1, adapter=adapter)
        service.submit(spec("live-worker"))
        self.assertTrue(adapter.started.wait(timeout=1))

        clock[0] = 101.0
        outcome = service.recover_stale_runs(stale_after_seconds=0)
        still_running = service.get("live-worker")
        self.assertEqual(outcome, {"recovered": [], "skipped_live": ["live-worker"]})
        self.assertEqual(still_running["status"], "RUNNING")
        self.assertEqual(still_running["attempts"][-1]["status"], "RUNNING")

        adapter.release.set()
        service.futures["live-worker"].result(timeout=2)
        self.assertEqual(service.get("live-worker")["status"], "SUCCEEDED")


class OpenStaSubprocessAdapterTests(unittest.TestCase):
    fixture_dir = Path(__file__).parents[1] / "docs/evidence/2026-09-24-real-sta"
    sta_path = Path("/tmp/eda-opensta-20260924/build/sta")
    liberty_path = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")

    @unittest.skipUnless(sta_path.is_file() and liberty_path.is_file(), "OpenSTA integration fixture is unavailable")
    def test_real_opensta_workload_collects_a_complete_report(self):
        adapter = OpenStaSubprocessAdapter(
            sta_path=self.sta_path,
            liberty_path=self.liberty_path,
            fixture_dir=self.fixture_dir,
            timeout_seconds=2,
        )

        result = adapter.run(spec("real-opensta-normal"))

        self.assertEqual(result.process_exit_code, 0)
        self.assertIn("EDA_LAB_REPORT_END", result.artifact_path.read_text(encoding="utf-8"))

    @unittest.skipUnless(sta_path.is_file() and liberty_path.is_file(), "OpenSTA integration fixture is unavailable")
    def test_timeout_terminates_a_real_opensta_child_before_the_report_finishes(self):
        with tempfile.TemporaryDirectory(prefix="eda-opensta-timeout-test-") as directory_name:
            fixture_dir = Path(directory_name)
            for name in ("tiny_mapped.v", "normal.sdc"):
                shutil.copy2(self.fixture_dir / name, fixture_dir / name)
            delayed = fixture_dir / "delayed.tcl"
            delayed.write_text("after 1000\n" + (self.fixture_dir / "run.tcl").read_text(encoding="utf-8"), encoding="utf-8")
            adapter = OpenStaSubprocessAdapter(
                sta_path=self.sta_path,
                liberty_path=self.liberty_path,
                fixture_dir=fixture_dir,
                script_name="delayed.tcl",
                timeout_seconds=0.05,
                termination_grace_seconds=0.5,
            )

            with self.assertRaisesRegex(TimeoutError, "termination=SIGTERM"):
                adapter.run(spec("real-opensta-timeout"))

    @unittest.skipUnless(sta_path.is_file() and liberty_path.is_file(), "OpenSTA integration fixture is unavailable")
    def test_confirmed_real_timeout_never_promotes_the_run_to_success(self):
        with tempfile.TemporaryDirectory(prefix="eda-opensta-timeout-service-") as directory_name:
            fixture_dir = Path(directory_name)
            for name in ("tiny_mapped.v", "normal.sdc"):
                shutil.copy2(self.fixture_dir / name, fixture_dir / name)
            (fixture_dir / "delayed.tcl").write_text(
                "after 1000\n" + (self.fixture_dir / "run.tcl").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            adapter = OpenStaSubprocessAdapter(
                sta_path=self.sta_path,
                liberty_path=self.liberty_path,
                fixture_dir=fixture_dir,
                script_name="delayed.tcl",
                timeout_seconds=0.05,
            )
            service = JobService(Store(), max_workers=1, max_attempts=1, adapter=adapter)
            service.submit(spec("real-opensta-timeout-service"))
            service.futures["real-opensta-timeout-service"].result(timeout=2)

            result = service.get("real-opensta-timeout-service")
            self.assertEqual(result["status"], "TIMED_OUT")
            self.assertEqual(result["trust_status"], "INVALID")
            self.assertEqual(result["attempts"][-1]["error_type"], "timeout")


if __name__ == "__main__":
    unittest.main()
