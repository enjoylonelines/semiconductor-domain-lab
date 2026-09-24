import threading
import unittest
from unittest.mock import patch

from eda_lab.models import AdapterRunResult, JobSpec
from eda_lab.runner import SyntheticTimingAdapter
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


if __name__ == "__main__":
    unittest.main()
