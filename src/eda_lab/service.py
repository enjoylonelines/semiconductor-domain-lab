from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
import time
from uuid import uuid4
from .models import AdapterRunResult, JobSpec
from .parser import parse_report
from .runner import AdapterCancelledError, SyntheticTimingAdapter
from .store import Store


class BackpressureError(RuntimeError):
    """The configured in-flight execution budget is exhausted."""


class JobService:
    def __init__(self, store: Store | None = None, max_workers: int = 4, max_attempts: int = 2, retry_delay_seconds: float = 0.01, adapter=None, resource_slots: int | None = None, worker_id: str = "local-worker", lease_seconds: float = 30, max_in_flight: int | None = None):
        self.store = store or Store()
        self.adapter = adapter or SyntheticTimingAdapter()
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.resource_slots = BoundedSemaphore(resource_slots) if resource_slots else None
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.max_in_flight = max_in_flight
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = Lock()
        self.futures = {}

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
            existing = self.store.get_run(spec.job_id)
            if existing:
                return existing
            if self.max_in_flight is not None:
                in_flight = sum(not future.done() for future in self.futures.values())
                if in_flight >= self.max_in_flight:
                    raise BackpressureError(f"in-flight execution budget exhausted: {self.max_in_flight}")
            self.store.create_run(spec.job_id, spec.design_id, spec.ip_family, spec.flow_name)
            future = self.executor.submit(self._execute, spec)
            self.futures[spec.job_id] = future
            return self.store.get_run(spec.job_id) or {}

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

    def _execute(self, spec: JobSpec) -> None:
        self.store.update_run(spec.job_id, status="RUNNING")
        for attempt_no in range(1, self.max_attempts + 1):
            acquired = False
            lease_token = None
            try:
                # Persist this boundary before adapter execution. An interruption after an
                # artifact is emitted can then be reconciled without inventing success.
                self.store.record_attempt(spec.job_id, attempt_no, "RUNNING", retry_class="not_classified")
                lease_token = uuid4().hex
                if not self.store.acquire_attempt_lease(spec.job_id, attempt_no, self.worker_id, lease_token, self.lease_seconds):
                    raise RuntimeError("attempt lease acquisition failed")
                if self.resource_slots:
                    self.resource_slots.acquire()
                    acquired = True
                adapter_result = self.adapter.run(spec)
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
                    self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="parse_invalid", error="; ".join(result.errors), artifact_path=str(artifact), retry_class="non_retryable")
                    self.store.update_run(spec.job_id, status="FAILED", **validation_fields, artifact_path=str(artifact), error="; ".join(result.errors))
                    return
                if result.semantic_status == "INVALID":
                    error = "; ".join(result.errors)
                    self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="semantic_invalid", error=error, artifact_path=str(artifact), retry_class="non_retryable")
                    self.store.update_run(spec.job_id, status="FAILED", **validation_fields, artifact_path=str(artifact), error=error)
                    if result.metrics:
                        self.store.save_metrics(spec.job_id, result.metrics)
                    return
                if process_exit_code is None:
                    error = "execution_outcome_unknown: adapter returned artifact without process exit code"
                    self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="execution_outcome_unknown", error=error, artifact_path=str(artifact), retry_class="non_retryable")
                    self.store.update_run(spec.job_id, status="FAILED", **validation_fields, artifact_path=str(artifact), error=error)
                    if result.metrics:
                        self.store.save_metrics(spec.job_id, result.metrics)
                    return
                if process_exit_code != 0:
                    error = f"tool_exit: exit code {process_exit_code}"
                    self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="tool_exit", error=error, artifact_path=str(artifact), retry_class="non_retryable")
                    self.store.update_run(spec.job_id, status="FAILED", **validation_fields, artifact_path=str(artifact), error=error)
                    if result.metrics:
                        self.store.save_metrics(spec.job_id, result.metrics)
                    return
                self.store.record_attempt(spec.job_id, attempt_no, "SUCCEEDED", artifact_path=str(artifact), retry_class="not_applicable")
                self.store.update_run(spec.job_id, status="SUCCEEDED", **validation_fields, artifact_path=str(artifact), error=None)
                if result.metrics:
                    self.store.save_metrics(spec.job_id, result.metrics)
                return
            except AdapterCancelledError as exc:
                self.store.record_attempt(spec.job_id, attempt_no, "CANCELLED", error_type="cancelled", error=str(exc), retry_class="non_retryable")
                self.store.update_run(spec.job_id, status="CANCELLED", trust_status="INVALID", error=str(exc))
                return
            except (TimeoutError, ConnectionError) as exc:
                error_type = "timeout" if isinstance(exc, TimeoutError) else "transport_error"
                self.store.record_attempt(spec.job_id, attempt_no, "RETRYABLE_FAILURE", error_type=error_type, error=str(exc), retry_class="retryable")
                if attempt_no < self.max_attempts:
                    time.sleep(self.retry_delay_seconds * attempt_no)
                    continue
                terminal_status = "TIMED_OUT" if isinstance(exc, TimeoutError) else "FAILED"
                self.store.update_run(
                    spec.job_id,
                    status=terminal_status,
                    trust_status="INVALID",
                    error=f"{error_type}: exhausted after {attempt_no} attempts",
                )
                return
            except Exception as exc:
                self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="execution_error", error=str(exc), retry_class="non_retryable")
                self.store.update_run(spec.job_id, status="FAILED", error=str(exc))
                return
            finally:
                if acquired:
                    self.resource_slots.release()

    def get(self, job_id: str) -> dict | None:
        return self.store.get_run(job_id)

    def recover_stale_runs(self, stale_after_seconds: float) -> dict[str, list[str]]:
        """Reconcile stale durable RUNNING records only after their local worker is gone."""
        cutoff = self.store.now() - stale_after_seconds
        recovered: list[str] = []
        skipped_live: list[str] = []
        for run in self.store.list_stale_running(cutoff):
            future = self.futures.get(run["job_id"])
            # A caller-side timeout does not establish that an adapter child has stopped.
            if future is not None and not future.done():
                skipped_live.append(run["job_id"])
                continue
            attempts = run["attempts"]
            if attempts and attempts[-1]["status"] == "RUNNING":
                self.store.record_attempt(
                    run["job_id"], attempts[-1]["attempt_no"], "ABANDONED",
                    error_type="worker_unavailable", error="stale running attempt recovered after worker ended",
                    retry_class="recovery_required",
                )
            self.store.update_run(run["job_id"], status="FAILED", error="recovery: stale RUNNING record without live worker")
            recovered.append(run["job_id"])
        return {"recovered": recovered, "skipped_live": skipped_live}
