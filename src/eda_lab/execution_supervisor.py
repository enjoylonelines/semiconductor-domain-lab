"""Host-local OpenSTA lifecycle observer for supervised execution."""

import os
import time
from threading import Event, Thread

from .models import JobSpec
from .parser import parse_report
from .service import JobService


class ExecutionSupervisor:
    """Claims one host request and persists a termination witness after adapter return."""

    def __init__(self, store, adapter, *, host_id: str, supervisor_id: str, lease_seconds: float = 30, progress_publisher=None):
        self.store = store
        self.adapter = adapter
        self.host_id = host_id
        self.supervisor_id = supervisor_id
        self.lease_seconds = lease_seconds
        self.progress_publisher = progress_publisher

    def _publish_progress(self, job_id: str, status: str, **fields) -> bool:
        if self.progress_publisher is None:
            return False
        try:
            return bool(self.progress_publisher.publish(job_id, status, **fields))
        except Exception:
            return False

    def _heartbeat_loop(self, stop: Event, request: dict) -> None:
        """Keep the accepted execution owner alive while this Supervisor owns its child."""
        payload = request["payload"]
        owner = payload["execution_owner"]
        interval = max(self.lease_seconds / 3, 0.01)
        while not stop.wait(interval):
            if not self.store.heartbeat_host_session(owner["session_id"], self.lease_seconds):
                return
            if not self.store.heartbeat_attempt(
                request["job_id"], request["attempt_no"], payload["lease_token"], self.lease_seconds
            ):
                return

    def run_once(self):
        request = self.store.claim_execution_request(self.host_id, self.supervisor_id)
        if request is None:
            return None
        def started(pid, _started_at):
            if not self.store.record_supervisor_process_started(request["execution_id"], self.supervisor_id, pid):
                raise RuntimeError("supervisor could not record child start")
        add_observer = getattr(self.adapter, "add_process_observer", None)
        remove_observer = add_observer(started) if callable(add_observer) else None
        heartbeat_stop = Event()
        heartbeat = Thread(target=self._heartbeat_loop, args=(heartbeat_stop, request), daemon=True)
        heartbeat.start()
        try:
            result = self.adapter.run(JobSpec(**request["payload"]["spec"]))
        except Exception as exc:
            self.store.record_termination_witness(
                request["execution_id"], kind="RUNTIME_TERMINATED", process_exit_code=None,
                artifact_path=None, detail=f"supervisor observed execution error: {exc}",
            )
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
            if callable(remove_observer):
                remove_observer()
            raise
        try:
            self.store.record_termination_witness(
                request["execution_id"], kind="PROCESS_EXITED", process_exit_code=result.process_exit_code,
                artifact_path=str(result.artifact_path), detail="supervisor observed adapter return",
            )
            hold_before_finalize = float(os.environ.get("EDA_SUPERVISOR_HOLD_BEFORE_FINALIZE_SECONDS", "0"))
            if hold_before_finalize > 0:
                time.sleep(hold_before_finalize)
            parsed = parse_report(result.artifact_path)
            fields = JobService._validation_fields(parsed, result.process_exit_code, result.execution_provenance)
            if parsed.parse_status == "OK" and parsed.semantic_status == "VALID" and result.process_exit_code == 0:
                ok = self.store.finalize_attempt_and_run(
                    request["job_id"], request["attempt_no"], request["payload"]["lease_token"],
                    "SUCCEEDED", "SUCCEEDED", artifact_path=str(result.artifact_path), retry_class="not_applicable",
                    run_fields=fields, execution_owner=request["payload"]["execution_owner"],
                )
            else:
                ok = self.store.finalize_attempt_and_run(
                    request["job_id"], request["attempt_no"], request["payload"]["lease_token"],
                    "FAILED", "FAILED", error_type="supervisor_validation_failed", error="supervisor rejected execution result",
                    artifact_path=str(result.artifact_path), retry_class="non_retryable", run_fields=fields,
                    execution_owner=request["payload"]["execution_owner"],
                )
            if not ok:
                raise RuntimeError("supervisor finalization lost its lease fence")
            self._publish_progress(
                request["job_id"],
                "SUCCEEDED" if parsed.parse_status == "OK" and parsed.semantic_status == "VALID" and result.process_exit_code == 0 else "FAILED",
                attempt_no=request["attempt_no"],
                host_id=self.host_id,
                supervisor_id=self.supervisor_id,
            )
            return request["execution_id"]
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
            if callable(remove_observer):
                remove_observer()
