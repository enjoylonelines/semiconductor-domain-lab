from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Lock
import time
from .models import JobSpec
from .parser import parse_report
from .runner import SyntheticTimingAdapter
from .store import Store


class JobService:
    def __init__(self, store: Store | None = None, max_workers: int = 4, max_attempts: int = 2, retry_delay_seconds: float = 0.01, adapter=None, resource_slots: int | None = None):
        self.store = store or Store()
        self.adapter = adapter or SyntheticTimingAdapter()
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.resource_slots = BoundedSemaphore(resource_slots) if resource_slots else None
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.lock = Lock()
        self.futures = {}

    def submit(self, spec: JobSpec) -> dict:
        with self.lock:
            existing = self.store.get_run(spec.job_id)
            if existing:
                return existing
            self.store.create_run(spec.job_id, spec.design_id, spec.ip_family, spec.flow_name)
            future = self.executor.submit(self._execute, spec)
            self.futures[spec.job_id] = future
            return self.store.get_run(spec.job_id) or {}

    def cancel(self, job_id: str) -> bool:
        with self.lock:
            future = self.futures.get(job_id)
            if future is None or not future.cancel():
                return False
            self.store.update_run(job_id, status="CANCELLED", error="cancelled before execution")
            return True

    def _execute(self, spec: JobSpec) -> None:
        self.store.update_run(spec.job_id, status="RUNNING")
        for attempt_no in range(1, self.max_attempts + 1):
            acquired = False
            try:
                if self.resource_slots:
                    self.resource_slots.acquire()
                    acquired = True
                artifact = self.adapter.run(spec)
                result = parse_report(artifact)
                if result.parse_status == "INVALID":
                    self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="parse_invalid", error="; ".join(result.errors), artifact_path=str(artifact))
                    self.store.update_run(spec.job_id, status="FAILED", parse_status="INVALID", check_status="UNKNOWN", completeness=result.completeness, provenance=result.provenance or {}, artifact_path=str(artifact), error="; ".join(result.errors))
                    return
                self.store.record_attempt(spec.job_id, attempt_no, "SUCCEEDED", artifact_path=str(artifact))
                self.store.update_run(spec.job_id, status="SUCCEEDED", parse_status=result.parse_status, check_status=result.check_status, completeness=result.completeness, provenance=result.provenance or {}, artifact_path=str(artifact), error=None)
                if result.metrics:
                    self.store.save_metrics(spec.job_id, result.metrics)
                return
            except (TimeoutError, ConnectionError) as exc:
                error_type = "timeout" if isinstance(exc, TimeoutError) else "transport_error"
                self.store.record_attempt(spec.job_id, attempt_no, "RETRYABLE_FAILURE", error_type=error_type, error=str(exc))
                if attempt_no < self.max_attempts:
                    time.sleep(self.retry_delay_seconds * attempt_no)
                    continue
                self.store.update_run(spec.job_id, status="FAILED", error=f"{error_type}: exhausted after {attempt_no} attempts")
                return
            except Exception as exc:
                self.store.record_attempt(spec.job_id, attempt_no, "FAILED", error_type="execution_error", error=str(exc))
                self.store.update_run(spec.job_id, status="FAILED", error=str(exc))
                return
            finally:
                if acquired:
                    self.resource_slots.release()

    def get(self, job_id: str) -> dict | None:
        return self.store.get_run(job_id)
