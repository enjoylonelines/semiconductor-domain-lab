"""Polling worker for the bounded PostgreSQL operational candidate."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, wait

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
        while max_jobs is None or len(completed) + len(active) < max_jobs:
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
