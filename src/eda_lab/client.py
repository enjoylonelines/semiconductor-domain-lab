"""A small HTTP caller that retries only explicit backpressure responses."""

from __future__ import annotations

import json
import random
import time
from typing import Callable
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .models import JobSpec


class BackpressureRetryExhausted(RuntimeError):
    """The server kept rejecting one immutable job submission."""


class RetryingJobClient:
    """Re-submit one immutable JobSpec after a server-provided backpressure delay."""

    def __init__(
        self,
        base_url: str,
        *,
        max_backpressure_retries: int = 3,
        jitter_seconds: float = 0.1,
        opener: Callable = urlopen,
        sleeper: Callable[[float], None] = time.sleep,
        random_float: Callable[[], float] = random.random,
    ):
        if max_backpressure_retries < 0 or jitter_seconds < 0:
            raise ValueError("retry count and jitter must be non-negative")
        self.base_url = base_url.rstrip("/")
        self.max_backpressure_retries = max_backpressure_retries
        self.jitter_seconds = jitter_seconds
        self.opener = opener
        self.sleeper = sleeper
        self.random_float = random_float

    @staticmethod
    def _payload(spec: JobSpec) -> dict:
        return {
            "job_id": spec.job_id,
            "design_id": spec.design_id,
            "ip_family": spec.ip_family,
            "flow_name": spec.flow_name,
            "corner": spec.corner,
            "worst_slack": spec.worst_slack,
            "unit": spec.unit,
            "duration_seconds": spec.duration_seconds,
        }

    def submit(self, spec: JobSpec) -> dict:
        payload = json.dumps(self._payload(spec), sort_keys=True).encode()
        for retry_number in range(self.max_backpressure_retries + 1):
            request = Request(
                f"{self.base_url}/jobs", data=payload,
                headers={"Content-Type": "application/json"}, method="POST",
            )
            try:
                with self.opener(request, timeout=5) as response:
                    return json.loads(response.read())
            except HTTPError as exc:
                try:
                    response = json.loads(exc.read())
                finally:
                    exc.close()
                if exc.code != 429 or not response.get("retryable"):
                    raise
                if retry_number == self.max_backpressure_retries:
                    raise BackpressureRetryExhausted(
                        f"job {spec.job_id} remained backpressured after {retry_number} retries"
                    ) from exc
                delay_seconds = response["retry_after_ms"] / 1000 + self.random_float() * self.jitter_seconds
                self.sleeper(delay_seconds)
        raise AssertionError("unreachable")
