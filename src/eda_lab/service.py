from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
import signal
import subprocess
from threading import BoundedSemaphore, Event, Lock, Thread, local
import time
from uuid import uuid4
from .models import AdapterRunResult, JobSpec
from .parser import parse_report
from .runner import AdapterCancelledError, SyntheticTimingAdapter
from .store import InFlightBudgetExhausted, Store


class BackpressureError(RuntimeError):
    """The configured in-flight execution budget is exhausted."""

    def __init__(self, budget: int, retry_after_seconds: float):
        self.budget = budget
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"in-flight execution budget exhausted: {budget}")


class IdempotencyConflict(RuntimeError):
    """One idempotency key was reused with a different immutable JobSpec."""


class JobService:
    def __init__(self, store: Store | None = None, max_workers: int = 4, max_attempts: int = 2, retry_delay_seconds: float = 0.01, adapter=None, resource_slots: int | None = None, worker_id: str = "local-worker", lease_seconds: float = 30, max_in_flight: int | None = None, enable_new_violation_index: bool = False, backpressure_retry_after_seconds: float = 1.0, execution_mode: str = "local", recovery_lease_seconds: float = 30, orphan_grace_seconds: float = 60):
        self.store = store or Store()
        self.adapter = adapter or SyntheticTimingAdapter()
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.resource_slots = BoundedSemaphore(resource_slots) if resource_slots else None
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        if recovery_lease_seconds <= 0 or orphan_grace_seconds <= 0:
            raise ValueError("recovery and orphan durations must be positive")
        self.recovery_lease_seconds = recovery_lease_seconds
        self.orphan_grace_seconds = orphan_grace_seconds
        self.max_in_flight = max_in_flight
        if execution_mode not in {"local", "external", "supervised"}:
            raise ValueError("execution_mode must be local or external")
        self.execution_mode = execution_mode
        if backpressure_retry_after_seconds <= 0:
            raise ValueError("backpressure_retry_after_seconds must be positive")
        self.backpressure_retry_after_seconds = backpressure_retry_after_seconds
        self.enable_new_violation_index = enable_new_violation_index
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = Lock()
        self.futures = {}
        self._process_context = local()
        self.execution_owner: dict[str, str] | None = None
        add_observer = getattr(self.adapter, "add_process_observer", None)
        if callable(add_observer):
            add_observer(self._record_adapter_process)

    def close(self) -> None:
        """Finish submitted local work, then release the Store connection."""
        self.executor.shutdown(wait=True)
        self.store.close()

    def set_execution_owner(self, owner: dict[str, str]) -> None:
        required = {"host_id", "host_epoch", "session_id"}
        if set(owner) != required or not all(owner.values()):
            raise ValueError("execution owner requires host_id, host_epoch, and session_id")
        if self.execution_owner is not None and self.execution_owner != owner:
            raise RuntimeError("a JobService instance cannot change Host Agent session")
        self.execution_owner = dict(owner)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.close()

    def _record_adapter_process(self, pid: int, started_at: float) -> None:
        context = getattr(self._process_context, "attempt", None)
        if context is None:
            return
        job_id, attempt_no, lease_token = context
        try:
            process_group_id = os.getpgid(pid)
        except (AttributeError, ProcessLookupError):
            process_group_id = None
        self.store.record_attempt_process(
            job_id, attempt_no, lease_token, pid, self.store.now(),
            process_identity=self._process_identity(pid), process_group_id=process_group_id,
            orphan_deadline=self.store.now() + self.orphan_grace_seconds,
        )

    @staticmethod
    def _process_identity(pid: int) -> str | None:
        """Return a local observation that distinguishes a reused PID when available."""
        try:
            observed = subprocess.check_output(
                ["ps", "-o", "lstart=", "-o", "command=", "-p", str(pid)], text=True, stderr=subprocess.DEVNULL
            ).strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            return None
        return observed or None

    @staticmethod
    def _spec_hash(spec: JobSpec) -> str:
        payload = {
            "job_id": spec.job_id,
            "design_id": spec.design_id,
            "ip_family": spec.ip_family,
            "flow_name": spec.flow_name,
            "corner": spec.corner,
            "worst_slack": spec.worst_slack,
            "unit": spec.unit,
            "duration_seconds": spec.duration_seconds,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def spec_payload(spec: JobSpec) -> dict:
        return {
            "job_id": spec.job_id, "design_id": spec.design_id, "ip_family": spec.ip_family,
            "flow_name": spec.flow_name, "corner": spec.corner, "worst_slack": spec.worst_slack,
            "unit": spec.unit, "duration_seconds": spec.duration_seconds,
        }

    @staticmethod
    def spec_from_payload(payload: dict) -> JobSpec:
        return JobSpec(**payload)

    @staticmethod
    def _trust_status(result, process_exit_code: int | None) -> str:
        if result.parse_status == "INVALID" or result.semantic_status == "INVALID":
            return "INVALID"
        if process_exit_code is None:
            return "UNKNOWN"
        if process_exit_code != 0:
            return "INVALID"
        if result.provenance_status != "VALID":
            return "UNKNOWN"
        if result.parse_status == "OK" and result.semantic_status == "VALID":
            return "TRUSTED"
        return "UNKNOWN"

    @classmethod
    def _validation_fields(cls, result, process_exit_code: int | None, execution_provenance: dict | None = None) -> dict:
        provenance = {**(execution_provenance or {}), **(result.provenance or {}), "observed_process_exit_code": process_exit_code}
        return {
            "parse_status": result.parse_status,
            "check_status": result.check_status,
            "completeness": result.completeness,
            "semantic_status": result.semantic_status,
            "provenance_status": result.provenance_status,
            "trust_status": cls._trust_status(result, process_exit_code),
            "provenance": provenance,
        }

    def submit(self, spec: JobSpec) -> dict:
        with self.lock:
            spec_hash = self._spec_hash(spec)
            existing = self.store.get_run(spec.job_id)
            if existing:
                if existing.get("spec_hash") != spec_hash:
                    raise IdempotencyConflict("idempotency key reused with different spec")
                return existing
            if self.max_in_flight is not None:
                in_flight = sum(not future.done() for future in self.futures.values())
                if in_flight >= self.max_in_flight:
                    raise BackpressureError(self.max_in_flight, self.backpressure_retry_after_seconds)
            try:
                created = self.store.create_run(
                    spec.job_id, spec.design_id, spec.ip_family, spec.flow_name, spec_hash,
                    max_in_flight=self.max_in_flight, spec_payload=self.spec_payload(spec),
                )
            except InFlightBudgetExhausted:
                raise BackpressureError(self.max_in_flight, self.backpressure_retry_after_seconds) from None
            if not created:
                existing = self.store.get_run(spec.job_id)
                if existing is None:
                    raise RuntimeError("run insertion was not visible after an idempotency conflict")
                if existing.get("spec_hash") != spec_hash:
                    raise IdempotencyConflict("idempotency key reused with different spec")
                return existing
            if self.execution_mode == "local":
                self.execute_claimed(spec)
            return self.store.get_run(spec.job_id) or {}

    def execute_claimed(self, spec: JobSpec):
        """Execute a Run already claimed by an external worker scheduler."""
        future = self.executor.submit(self._execute, spec)
        self.futures[spec.job_id] = future
        return future

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            future = self.futures.get(job_id)
            if future is None:
                return False
            if future.cancel():
                self.store.update_run(job_id, status="CANCELLED", trust_status="INVALID", error="cancelled before execution")
                return True
            cancel_adapter = getattr(self.adapter, "cancel", None)
            return bool(callable(cancel_adapter) and cancel_adapter(job_id))

    def _heartbeat_loop(self, stop: Event, job_id: str, attempt_no: int, lease_token: str) -> None:
        interval = max(self.lease_seconds / 3, 0.01)
        while not stop.wait(interval):
            if self.execution_owner is not None and not self.store.heartbeat_host_session(
                self.execution_owner["session_id"], self.lease_seconds
            ):
                return
            if not self.store.heartbeat_attempt(job_id, attempt_no, lease_token, self.lease_seconds):
                return

    def _transition_attempt(self, job_id: str, attempt_no: int, lease_token: str, status: str, **fields) -> None:
        if not self.store.transition_attempt(job_id, attempt_no, lease_token, status, **fields):
            raise RuntimeError("attempt terminal write lost its lease fence")

    def _finalize_attempt_and_run(self, job_id: str, attempt_no: int, lease_token: str, attempt_status: str,
                                  run_status: str, **fields) -> None:
        run_fields = fields.pop("run_fields", {})
        if not self.store.finalize_attempt_and_run(
            job_id, attempt_no, lease_token, attempt_status, run_status, run_fields=run_fields,
            execution_owner=self.execution_owner, **fields
        ):
            raise RuntimeError("attempt and run terminal write lost its lease fence")

    def _execute(self, spec: JobSpec) -> None:
        self.store.update_run(spec.job_id, status="RUNNING")
        for attempt_no in range(1, self.max_attempts + 1):
            acquired = False
            lease_token = None
            heartbeat_stop = None
            heartbeat_thread = None
            try:
                # Persist this boundary before adapter execution. An interruption after an
                # artifact is emitted can then be reconciled without inventing success.
                self.store.record_attempt(spec.job_id, attempt_no, "RUNNING", retry_class="not_classified")
                lease_token = uuid4().hex
                if not self.store.acquire_attempt_lease(spec.job_id, attempt_no, self.worker_id, lease_token, self.lease_seconds):
                    raise RuntimeError("attempt lease acquisition failed")
                execution_id = uuid4().hex
                if self.execution_owner is not None and not self.store.record_attempt_execution(
                    spec.job_id, attempt_no, lease_token, **self.execution_owner, execution_id=execution_id
                ):
                    raise RuntimeError("attempt execution owner registration failed")
                if self.execution_mode == "supervised":
                    if self.execution_owner is None:
                        raise RuntimeError("supervised execution requires a Host Agent owner")
                    if not self.store.enqueue_execution_request(
                        execution_id, spec.job_id, attempt_no, self.execution_owner["host_id"],
                        {"spec": self.spec_payload(spec), "lease_token": lease_token, "execution_owner": self.execution_owner},
                    ):
                        raise RuntimeError("execution request enqueue failed")
                    return
                heartbeat_stop = Event()
                heartbeat_thread = Thread(
                    target=self._heartbeat_loop, args=(heartbeat_stop, spec.job_id, attempt_no, lease_token), daemon=True
                )
                heartbeat_thread.start()
                if self.resource_slots:
                    self.resource_slots.acquire()
                    acquired = True
                self._process_context.attempt = (spec.job_id, attempt_no, lease_token)
                try:
                    adapter_result = self.adapter.run(spec)
                finally:
                    del self._process_context.attempt
                if not self.store.heartbeat_attempt(spec.job_id, attempt_no, lease_token, self.lease_seconds):
                    raise RuntimeError("attempt lease was lost before result collection")
                if isinstance(adapter_result, AdapterRunResult):
                    artifact = adapter_result.artifact_path
                    process_exit_code = adapter_result.process_exit_code
                    execution_provenance = adapter_result.execution_provenance
                else:
                    # Temporary diagnostic bridge: a bare path cannot prove execution success.
                    artifact = adapter_result
                    process_exit_code = None
                    execution_provenance = None
                result = parse_report(artifact)
                validation_fields = self._validation_fields(result, process_exit_code, execution_provenance)
                if result.parse_status == "INVALID":
                    self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "FAILED", "FAILED", error_type="parse_invalid", error="; ".join(result.errors), artifact_path=str(artifact), retry_class="non_retryable", run_fields=validation_fields)
                    return
                if result.semantic_status == "INVALID":
                    error = "; ".join(result.errors)
                    self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "FAILED", "FAILED", error_type="semantic_invalid", error=error, artifact_path=str(artifact), retry_class="non_retryable", run_fields=validation_fields)
                    if result.metrics:
                        self.store.save_metrics(spec.job_id, result.metrics)
                    return
                if process_exit_code is None:
                    error = "execution_outcome_unknown: adapter returned artifact without process exit code"
                    self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "FAILED", "FAILED", error_type="execution_outcome_unknown", error=error, artifact_path=str(artifact), retry_class="non_retryable", run_fields=validation_fields)
                    if result.metrics:
                        self.store.save_metrics(spec.job_id, result.metrics)
                    return
                if process_exit_code != 0:
                    error = f"tool_exit: exit code {process_exit_code}"
                    self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "FAILED", "FAILED", error_type="tool_exit", error=error, artifact_path=str(artifact), retry_class="non_retryable", run_fields=validation_fields)
                    if result.metrics:
                        self.store.save_metrics(spec.job_id, result.metrics)
                    return
                self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "SUCCEEDED", "SUCCEEDED", artifact_path=str(artifact), retry_class="not_applicable", run_fields=validation_fields)
                if result.metrics:
                    self.store.save_metrics(spec.job_id, result.metrics)
                return
            except AdapterCancelledError as exc:
                self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "CANCELLED", "CANCELLED", error_type="cancelled", error=str(exc), retry_class="non_retryable", run_fields={"trust_status": "INVALID"})
                return
            except (TimeoutError, ConnectionError) as exc:
                error_type = "timeout" if isinstance(exc, TimeoutError) else "transport_error"
                if attempt_no < self.max_attempts:
                    self._transition_attempt(spec.job_id, attempt_no, lease_token, "RETRYABLE_FAILURE", error_type=error_type, error=str(exc), retry_class="retryable")
                    time.sleep(self.retry_delay_seconds * attempt_no)
                    continue
                terminal_status = "TIMED_OUT" if isinstance(exc, TimeoutError) else "FAILED"
                self._finalize_attempt_and_run(
                    spec.job_id, attempt_no, lease_token, "RETRYABLE_FAILURE", terminal_status,
                    error_type=error_type, error=f"{error_type}: exhausted after {attempt_no} attempts",
                    retry_class="retryable", run_fields={"trust_status": "INVALID"},
                )
                return
            except Exception as exc:
                self._finalize_attempt_and_run(spec.job_id, attempt_no, lease_token, "FAILED", "FAILED", error_type="execution_error", error=str(exc), retry_class="non_retryable")
                return
            finally:
                if heartbeat_stop is not None:
                    heartbeat_stop.set()
                if heartbeat_thread is not None:
                    heartbeat_thread.join(timeout=1)
                if acquired:
                    self.resource_slots.release()

    def get(self, job_id: str) -> dict | None:
        return self.store.get_run(job_id)

    def recover_stale_runs(self, stale_after_seconds: float) -> dict[str, list[str]]:
        """Reconcile stale durable RUNNING records only after their local worker is gone."""
        cutoff = self.store.now() - stale_after_seconds
        recovered: list[str] = []
        skipped_live: list[str] = []
        skipped_live_child: list[str] = []
        skipped_active_lease: list[str] = []
        skipped_recovery_claim: list[str] = []
        orphan_termination_requested: list[str] = []
        deferred_remote_execution: list[str] = []
        expired_leases = set(self.store.list_expired_leased_attempts())
        for run in self.store.list_stale_running(cutoff):
            future = self.futures.get(run["job_id"])
            # A caller-side timeout does not establish that an adapter child has stopped.
            if future is not None and not future.done():
                skipped_live.append(run["job_id"])
                continue
            attempts = run["attempts"]
            if not attempts:
                self.store.update_run(run["job_id"], status="FAILED", error="recovery: stale RUNNING record without an Attempt")
                recovered.append(run["job_id"])
                continue
            attempt = attempts[-1]
            if attempt.get("execution_host_session") and (
                self.execution_owner is None
                or attempt["execution_host_session"] != self.execution_owner["session_id"]
            ):
                # A Host Agent may only observe a child it owns locally. A remote
                # PID is neither evidence of life nor authorization to signal it.
                witness = self.store.get_termination_witness(attempt.get("execution_id"))
                if witness is None or witness["kind"] not in {"RUNTIME_TERMINATED", "PROCESS_EXITED"}:
                    deferred_remote_execution.append(run["job_id"])
                    continue
            if attempt["lease_token"] and (run["job_id"], attempt["attempt_no"]) not in expired_leases:
                skipped_active_lease.append(run["job_id"])
                continue
            recovery_token = uuid4().hex
            if not self.store.claim_recovery(
                run["job_id"], attempt["attempt_no"], self.worker_id, recovery_token, self.recovery_lease_seconds
            ):
                skipped_recovery_claim.append(run["job_id"])
                continue
            if attempt["process_pid"] is not None:
                try:
                    os.kill(attempt["process_pid"], 0)
                except ProcessLookupError:
                    pass
                else:
                    identity_matches = attempt.get("process_identity") in {None, self._process_identity(attempt["process_pid"])}
                    deadline_expired = attempt.get("orphan_deadline") is not None and self.store.now() >= attempt["orphan_deadline"]
                    if not deadline_expired:
                        self.store.release_recovery_claim(run["job_id"], attempt["attempt_no"], recovery_token)
                        skipped_live_child.append(run["job_id"])
                        continue
                    if identity_matches and attempt.get("process_group_id") == attempt["process_pid"]:
                        try:
                            os.killpg(attempt["process_group_id"], signal.SIGTERM)
                        except (AttributeError, ProcessLookupError, PermissionError):
                            pass
                        else:
                            self.store.release_recovery_claim(run["job_id"], attempt["attempt_no"], recovery_token)
                            orphan_termination_requested.append(run["job_id"])
                            continue
                    if not self.store.finalize_recovery(
                        run["job_id"], attempt["attempt_no"], recovery_token,
                        error_type="orphan_deadline_identity_unknown",
                        error="recovery: orphan deadline expired without a safely terminable child identity",
                    ):
                        skipped_recovery_claim.append(run["job_id"])
                    else:
                        recovered.append(run["job_id"])
                    continue
            witness = self.store.get_termination_witness(attempt.get("execution_id"))
            if witness is not None and witness["kind"] in {"RUNTIME_TERMINATED", "PROCESS_EXITED"}:
                error_type = "supervisor_terminated"
                error = "recovery: supervised execution ended without an accepted completion"
            else:
                error_type = "worker_unavailable"
                error = "recovery: stale RUNNING record without live worker"
            if self.store.finalize_recovery(
                run["job_id"], attempt["attempt_no"], recovery_token,
                error_type=error_type, error=error,
            ):
                recovered.append(run["job_id"])
            else:
                skipped_recovery_claim.append(run["job_id"])
        result = {"recovered": recovered, "skipped_live": skipped_live}
        if skipped_active_lease:
            result["skipped_active_lease"] = skipped_active_lease
        if skipped_live_child:
            result["skipped_live_child"] = skipped_live_child
        if skipped_recovery_claim:
            result["skipped_recovery_claim"] = skipped_recovery_claim
        if orphan_termination_requested:
            result["orphan_termination_requested"] = orphan_termination_requested
        if deferred_remote_execution:
            result["deferred_remote_execution"] = deferred_remote_execution
        return result
