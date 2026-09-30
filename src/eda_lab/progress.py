"""Best-effort progress events for transient UI/status delivery.

PostgreSQL remains authoritative. A publisher failure must never change Run or
Attempt correctness.
"""

from __future__ import annotations

import json
import time
from typing import Any


class NullProgressPublisher:
    def publish(self, job_id: str, status: str, **fields: Any) -> bool:
        return False

    def close(self) -> None:
        return None


class RedisProgressPublisher:
    """Publish ephemeral Run progress events to one Redis Pub/Sub channel."""

    def __init__(self, client, *, channel: str = "eda:run-progress", now=None):
        self.client = client
        self.channel = channel
        self._now = now or time.time

    @classmethod
    def from_url(cls, url: str, *, channel: str = "eda:run-progress"):
        import redis

        return cls(
            redis.Redis.from_url(
                url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            ),
            channel=channel,
        )

    def publish(self, job_id: str, status: str, **fields: Any) -> bool:
        event = {
            "job_id": job_id,
            "status": status,
            "observed_at": self._now(),
            **fields,
        }
        try:
            self.client.publish(
                self.channel,
                json.dumps(event, sort_keys=True, separators=(",", ":")),
            )
        except Exception:
            # Pub/Sub is intentionally not part of the execution correctness
            # boundary. Clients recover current state from PostgreSQL.
            return False
        return True

    def close(self) -> None:
        close = getattr(self.client, "close", None)
        if callable(close):
            close()
