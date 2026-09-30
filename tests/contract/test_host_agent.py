import unittest

from eda_lab.host_agent import HostAgent
from eda_lab.execution_supervisor import ExecutionSupervisor
from eda_lab.models import JobSpec
from eda_lab.runner import SyntheticTimingAdapter
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

    def test_termination_witness_requires_a_durable_execution_request(self):
        self.assertFalse(self.store.record_termination_witness(
            "missing", kind="RUNTIME_TERMINATED", process_exit_code=None, artifact_path=None, detail="container removed"
        ))
        self.assertTrue(self.store.enqueue_execution_request(
            "execution-a", "job-a", 1, "host-a", {"fixture": "normal"}
        ))
        self.assertTrue(self.store.record_termination_witness(
            "execution-a", kind="RUNTIME_TERMINATED", process_exit_code=None, artifact_path=None, detail="container removed"
        ))
        self.assertFalse(self.store.record_termination_witness(
            "execution-a", kind="RUNTIME_TERMINATED", process_exit_code=None, artifact_path=None, detail="duplicate"
        ))

    def test_supervised_worker_enqueues_an_execution_request_without_running_the_adapter(self):
        service = JobService(self.store, max_workers=1, max_attempts=1, worker_id="worker-a",
                             execution_mode="supervised", lease_seconds=10)
        self.addCleanup(service.close)
        agent = HostAgent(self.store, service, host_id="host-a", host_epoch="boot-a", session_id="a-1")
        agent.start()
        spec = JobSpec("supervised-run", "d", "ip", "timing", "TT", 0.1, "ns")
        service.submit(spec)
        service.execute_claimed(spec).result(timeout=2)
        request = self.store.connection.execute("SELECT * FROM execution_requests").fetchone()
        self.assertEqual(request["job_id"], spec.job_id)
        self.assertEqual(request["host_id"], "host-a")
        self.assertEqual(self.store.get_run(spec.job_id)["status"], "RUNNING")

    def test_live_host_agent_refreshes_only_queued_delivery_attempt_leases(self):
        job_id = "queued-delivery-lease"
        self.store.create_run(job_id, "d", "ip", "timing")
        self.store.update_run(job_id, status="RUNNING")
        self.store.record_attempt(job_id, 1, "RUNNING")
        self.assertTrue(self.store.acquire_attempt_lease(job_id, 1, "worker-a", "token", 10))
        service = self.service("worker-a")
        agent = HostAgent(self.store, service, host_id="host-a", host_epoch="boot-a", session_id="session-a")
        agent.start()
        self.assertTrue(self.store.record_attempt_execution(
            job_id, 1, "token", **agent.owner.as_dict(), execution_id="execution-a",
        ))
        self.assertTrue(self.store.enqueue_execution_request("execution-a", job_id, 1, "host-a", {}))

        self.clock[0] = 109.0
        self.assertTrue(agent.heartbeat())
        self.assertEqual(self.store.get_run(job_id)["attempts"][-1]["lease_expires_at"], 119.0)

        self.assertIsNotNone(self.store.claim_execution_request("host-a", "supervisor-a"))
        self.clock[0] = 118.0
        self.assertTrue(agent.heartbeat())
        self.assertEqual(self.store.get_run(job_id)["attempts"][-1]["lease_expires_at"], 119.0)

    def test_only_one_supervisor_claims_a_host_request(self):
        self.store.enqueue_execution_request("execution-a", "job-a", 1, "host-a", {"fixture": "normal"})
        first = self.store.claim_execution_request("host-a", "supervisor-a")
        second = self.store.claim_execution_request("host-a", "supervisor-b")
        self.assertEqual(first["execution_id"], "execution-a")
        self.assertIsNone(second)

    def test_supervisor_writes_process_exit_witness(self):
        spec = JobSpec("supervisor-run", "d", "ip", "timing", "TT", 0.1, "ns")
        self.store.create_run(spec.job_id, "d", "ip", "timing")
        self.store.update_run(spec.job_id, status="RUNNING")
        self.store.record_attempt(spec.job_id, 1, "RUNNING")
        self.store.acquire_attempt_lease(spec.job_id, 1, "worker-a", "token", 10)
        self.store.start_host_session("host-a", "boot-a", "session-a", 10)
        self.store.record_attempt_execution(spec.job_id, 1, "token", host_id="host-a", host_epoch="boot-a", session_id="session-a", execution_id="execution-a")
        self.store.enqueue_execution_request("execution-a", spec.job_id, 1, "host-a", {"spec": JobService.spec_payload(spec), "lease_token": "token", "execution_owner": {"host_id": "host-a", "host_epoch": "boot-a", "session_id": "session-a"}})
        events = []
        publisher = type(
            "Recorder",
            (),
            {"publish": lambda _self, job_id, status, **fields: events.append((job_id, status, fields)) or True},
        )()
        supervisor = ExecutionSupervisor(
            self.store,
            SyntheticTimingAdapter(),
            host_id="host-a",
            supervisor_id="supervisor-a",
            progress_publisher=publisher,
        )
        self.assertEqual(supervisor.run_once(), "execution-a")
        witness = self.store.connection.execute("SELECT kind,process_exit_code FROM execution_witnesses WHERE execution_id='execution-a'").fetchone()
        self.assertEqual((witness["kind"], witness["process_exit_code"]), ("PROCESS_EXITED", 0))
        self.assertEqual(self.store.get_run(spec.job_id)["status"], "SUCCEEDED")
        request = self.store.connection.execute("SELECT status FROM execution_requests WHERE execution_id='execution-a'").fetchone()
        self.assertEqual(request["status"], "COMPLETED")
        self.assertEqual(events[0][0:2], (spec.job_id, "SUCCEEDED"))
        self.assertEqual(events[0][2]["host_id"], "host-a")

    def test_foreign_runtime_termination_witness_allows_safe_failure_closure(self):
        job_id = "remote-terminated"
        self.store.create_run(job_id, "d", "ip", "timing")
        self.store.update_run(job_id, status="RUNNING")
        self.store.record_attempt(job_id, 1, "RUNNING")
        self.store.acquire_attempt_lease(job_id, 1, "a", "token", 1)
        self.store.start_host_session("host-a", "boot-a", "session-a", 1)
        self.store.record_attempt_execution(job_id, 1, "token", host_id="host-a", host_epoch="boot-a", session_id="session-a", execution_id="execution-a")
        self.store.enqueue_execution_request("execution-a", job_id, 1, "host-a", {})
        self.store.record_termination_witness("execution-a", kind="RUNTIME_TERMINATED", process_exit_code=None, artifact_path=None, detail="runtime removed")
        self.clock[0] = 102
        service = self.service("worker-b")
        outcome = service.recover_stale_runs(0)
        self.assertEqual(outcome["recovered"], [job_id])
        self.assertEqual(self.store.get_run(job_id)["status"], "FAILED")

    def test_foreign_process_exit_witness_never_implies_accepted_success(self):
        job_id = "remote-exited-before-finalization"
        self.store.create_run(job_id, "d", "ip", "timing")
        self.store.update_run(job_id, status="RUNNING")
        self.store.record_attempt(job_id, 1, "RUNNING")
        self.store.acquire_attempt_lease(job_id, 1, "a", "token", 1)
        self.store.start_host_session("host-a", "boot-a", "session-a", 1)
        self.store.record_attempt_execution(job_id, 1, "token", host_id="host-a", host_epoch="boot-a", session_id="session-a", execution_id="execution-a")
        self.store.enqueue_execution_request("execution-a", job_id, 1, "host-a", {})
        self.store.record_termination_witness("execution-a", kind="PROCESS_EXITED", process_exit_code=0,
                                              artifact_path="/tmp/report", detail="child exited before supervisor finalization")
        self.clock[0] = 102
        service = self.service("worker-b")
        outcome = service.recover_stale_runs(0)
        run = self.store.get_run(job_id)
        self.assertEqual(outcome["recovered"], [job_id])
        self.assertEqual(run["status"], "FAILED")
        self.assertEqual(run["attempts"][-1]["status"], "ABANDONED")
        self.assertEqual(run["attempts"][-1]["error_type"], "supervisor_terminated")


if __name__ == "__main__":
    unittest.main()
