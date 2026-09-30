"""Host-local execution ownership for the multi-host validation profile."""

from __future__ import annotations

from dataclasses import dataclass
from threading import Event
import time
from uuid import uuid4

from .worker import PostgresWorker


@dataclass(frozen=True)
class ExecutionOwner:
    """A fenced Host Agent session, not a remotely observable PID."""

    host_id: str
    host_epoch: str
    session_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "host_id": self.host_id,
            "host_epoch": self.host_epoch,
            "session_id": self.session_id,
        }


class HostAgent:
    """Registers one host-local execution session and drives a Worker."""

    def __init__(self, store, service, *, host_id: str, host_epoch: str, session_id: str | None = None):
        if not host_id or not host_epoch:
            raise ValueError("host_id and host_epoch are required")
        self.store = store
        self.service = service
        self.owner = ExecutionOwner(host_id, host_epoch, session_id or uuid4().hex)
        self.worker = PostgresWorker(store, service)
        self.started = False

    def start(self) -> ExecutionOwner:
        self.store.start_host_session(**self.owner.as_dict(), ttl_seconds=self.service.lease_seconds)
        self.service.set_execution_owner(self.owner.as_dict())
        self.started = True
        return self.owner

    def heartbeat(self) -> bool:
        if not self.started:
            self.start()
        if not self.store.heartbeat_host_session(self.owner.session_id, self.service.lease_seconds):
            return False
        refresh_pending = getattr(self.store, "heartbeat_queued_execution_attempts", None)
        if callable(refresh_pending):
            refresh_pending(self.owner.session_id, self.service.lease_seconds)
        return True

    def drain(self, **kwargs) -> list[str]:
        if not self.heartbeat():
            raise RuntimeError("host agent session was superseded")
        return self.worker.drain(**kwargs)

    def serve(self, *, concurrency: int = 1, poll_seconds: float = 0.5, stop: Event | None = None) -> list[str]:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        stop = stop or Event()
        completed: list[str] = []
        while not stop.is_set():
            completed.extend(self.drain(concurrency=concurrency))
            stop.wait(poll_seconds)
        return completed
