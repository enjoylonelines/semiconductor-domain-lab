import os
import unittest
from uuid import uuid4

from eda_lab.host_agent import HostAgent
from eda_lab.postgres_store import PostgresStore
from eda_lab.service import JobService


DSN = os.environ.get("EDA_POSTGRES_TEST_DSN")


@unittest.skipUnless(DSN, "set EDA_POSTGRES_TEST_DSN for a dedicated disposable PostgreSQL database")
class PostgresHostAgentContractTests(unittest.TestCase):
    def setUp(self):
        self.clock = [100.0]
        self.prefix = uuid4().hex
        self.first_store = PostgresStore(DSN, now=lambda: self.clock[0])
        self.second_store = PostgresStore(DSN, now=lambda: self.clock[0])
        self.addCleanup(self.first_store.close)
        self.addCleanup(self.second_store.close)

    def service(self, store, worker_id):
        service = JobService(store, max_workers=1, max_attempts=1, worker_id=worker_id,
                             execution_mode="external", lease_seconds=1)
        self.addCleanup(service.close)
        return service

    def test_two_independent_postgres_agents_fence_an_old_host_epoch(self):
        job_id = f"{self.prefix}-host-epoch"
        self.first_store.create_run(job_id, "d", "ip", "timing")
        self.first_store.update_run(job_id, status="RUNNING")
        self.first_store.record_attempt(job_id, 1, "RUNNING", retry_class="not_classified")
        self.assertTrue(self.first_store.acquire_attempt_lease(job_id, 1, "agent-a", "attempt-token", 1))

        first_service = self.service(self.first_store, "agent-a")
        first = HostAgent(self.first_store, first_service, host_id="host-a", host_epoch="boot-a", session_id=f"{self.prefix}-a")
        first.start()
        self.assertTrue(self.first_store.record_attempt_execution(
            job_id, 1, "attempt-token", **first.owner.as_dict(), execution_id="execution-a",
        ))

        second_service = self.service(self.second_store, "agent-a-restarted")
        second = HostAgent(self.second_store, second_service, host_id="host-a", host_epoch="boot-b", session_id=f"{self.prefix}-b")
        second.start()
        self.assertFalse(self.first_store.finalize_attempt_and_run(
            job_id, 1, "attempt-token", "SUCCEEDED", "SUCCEEDED", execution_owner=first.owner.as_dict(),
        ))

        self.clock[0] = 102.0
        outcome = second_service.recover_stale_runs(stale_after_seconds=0)
        self.assertEqual(outcome["deferred_remote_execution"], [job_id])
        result = self.second_store.get_run(job_id)
        self.assertEqual(result["status"], "RUNNING")
        self.assertEqual(result["attempts"][-1]["execution_host_epoch"], "boot-a")
        self.second_store.update_run(job_id, status="FAILED", error="test cleanup after deferred remote execution")


if __name__ == "__main__":
    unittest.main()
