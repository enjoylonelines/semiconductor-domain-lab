"""Polling worker for the bounded PostgreSQL operational candidate."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, wait
from threading import Event

from .service import JobService


class PostgresWorker:
    """Claims queued Runs from a central store and executes them one at a time."""

    def __init__(self, store, service: JobService):
        self.store = store
        self.service = service

    def drain(self, max_jobs: int | None = None, concurrency: int = 1) -> list[str]:
        if concurrency < 1:
            raise ValueError("concurrency must be positive")
        completed: list[str] = []
        active = {}
        # Recovery is part of the Worker responsibility for the bounded
        # same-host profile. A database recovery claim serializes this against
        # other Workers before any local process observation occurs.
        self.service.recover_stale_runs(stale_after_seconds=self.service.lease_seconds)
        while max_jobs is None or len(completed) + len(active) < max_jobs:
            if self.service.execution_mode == "supervised" and self.service.execution_owner is not None:
                host_id = self.service.execution_owner["host_id"]
                if self.store.count_active_execution_requests(host_id) >= self.service.max_in_flight:
                    break
            if len(active) >= concurrency:
                done, _ = wait(active, return_when=FIRST_COMPLETED)
                for future in done:
                    completed.append(active.pop(future))
                continue
            payload = self.store.claim_next_run(self.service.worker_id)
            if payload is None:
                break
            spec = self.service.spec_from_payload(payload)
            active[self.service.execute_claimed(spec)] = spec.job_id
        for future, job_id in active.items():
            future.result()
            completed.append(job_id)
        return completed

    def serve(self, *, concurrency: int = 1, poll_seconds: float = 0.5, stop: Event | None = None) -> list[str]:
        """Run bounded claim and recovery scans until a caller stops the Worker."""
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        stop = stop or Event()
        completed: list[str] = []
        while not stop.is_set():
            before = len(completed)
            completed.extend(self.drain(concurrency=concurrency))
            if len(completed) == before:
                stop.wait(poll_seconds)
        return completed
