import unittest

from eda_lab.host_agent import HostAgent
from eda_lab.models import JobSpec
from eda_lab.service import JobService
from eda_lab.store import Store


class HostAgentContractTests(unittest.TestCase):
    def setUp(self):
        self.clock = [100.0]
        self.store = Store(now=lambda: self.clock[0])
        self.addCleanup(self.store.close)

    def service(self, worker_id: str) -> JobService:
        service = JobService(self.store, max_workers=1, max_attempts=1, worker_id=worker_id,
                             execution_mode="external", lease_seconds=10)
        self.addCleanup(service.close)
        return service

    def test_host_agent_records_fenced_execution_identity(self):
        service = self.service("agent-a-worker")
        spec = JobSpec("host-agent-run", "d", "ip", "timing", "TT", 0.1, "ns")
        service.submit(spec)
        agent = HostAgent(self.store, service, host_id="host-a", host_epoch="boot-a", session_id="a-1")

        agent.start()
        service.execute_claimed(spec).result(timeout=2)
        attempt = self.store.get_run(spec.job_id)["attempts"][-1]
        self.assertEqual(attempt["execution_host_id"], "host-a")
        self.assertEqual(attempt["execution_host_epoch"], "boot-a")
        self.assertEqual(attempt["execution_host_session"], "a-1")
        self.assertTrue(attempt["execution_id"])

    def test_new_host_epoch_fences_old_session_completion_and_defers_foreign_recovery(self):
        job_id = "host-epoch-fence"
        self.store.create_run(job_id, "d", "ip", "timing")
        self.store.update_run(job_id, status="RUNNING")
        self.store.record_attempt(job_id, 1, "RUNNING", retry_class="not_classified")
        self.assertTrue(self.store.acquire_attempt_lease(job_id, 1, "agent-a", "attempt-token", 1))

        first_service = self.service("agent-a")
        first = HostAgent(self.store, first_service, host_id="host-a", host_epoch="boot-a", session_id="a-1")
        first.start()
        self.assertTrue(self.store.record_attempt_execution(
            job_id, 1, "attempt-token", **first.owner.as_dict(), execution_id="execution-a",
        ))

        second_service = self.service("agent-a-restarted")
        second = HostAgent(self.store, second_service, host_id="host-a", host_epoch="boot-b", session_id="a-2")
        second.start()
        self.assertFalse(self.store.heartbeat_host_session("a-1", 10))
        self.assertFalse(self.store.finalize_attempt_and_run(
            job_id, 1, "attempt-token", "SUCCEEDED", "SUCCEEDED", execution_owner=first.owner.as_dict(),
        ))

        self.clock[0] = 102.0
        outcome = second_service.recover_stale_runs(stale_after_seconds=0)
        self.assertEqual(outcome["deferred_remote_execution"], [job_id])
        self.assertEqual(self.store.get_run(job_id)["status"], "RUNNING")


if __name__ == "__main__":
    unittest.main()
