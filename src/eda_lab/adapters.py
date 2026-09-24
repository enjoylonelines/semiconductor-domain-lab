from __future__ import annotations

import json
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class Lease:
    resource_key: str
    owner_id: str
    acquired_at: float


@dataclass(frozen=True)
class RawResult:
    source_kind: str
    adapter: str
    execution_status: str
    transport_status: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class ArtifactSet:
    paths: tuple[Path, ...]
    source_kind: str
    adapter: str


class ExternalAdapter(Protocol):
    def acquire(self, spec: dict[str, Any]) -> Lease: ...
    def execute(self, lease: Lease, spec: dict[str, Any]) -> RawResult: ...
    def collect(self, raw: RawResult) -> ArtifactSet: ...
    def release(self, lease: Lease) -> None: ...


class FixtureAdapter:
    """Synthetic lifecycle adapter; no device, SDK, license, or electrical I/O."""

    adapter_name = "fixture"
    _locks: dict[str, threading.Lock] = {}
    _locks_guard = threading.Lock()

    def __init__(self, resource_key: str = "fixture-resource"):
        self.resource_key = resource_key
        with self._locks_guard:
            self._locks.setdefault(resource_key, threading.Lock())

    def acquire(self, spec: dict[str, Any]) -> Lease:
        owner_id = str(spec["job_id"])
        lock = self._locks[self.resource_key]
        if not lock.acquire(blocking=False):
            raise RuntimeError("resource_unavailable")
        return Lease(self.resource_key, owner_id, time.time())

    def execute(self, lease: Lease, spec: dict[str, Any]) -> RawResult:
        if lease.resource_key != self.resource_key:
            raise ValueError("lease does not belong to adapter resource")
        profile = spec.get("profile", "normal")
        if profile == "timeout":
            raise TimeoutError("synthetic timeout")
        if profile == "transport_error":
            raise ConnectionError("synthetic transport error")
        return RawResult("fixture", self.adapter_name, "SUCCEEDED", "OK", self._payload(spec))

    def collect(self, raw: RawResult) -> ArtifactSet:
        directory = Path(tempfile.mkdtemp(prefix=f"eda-lab-{raw.adapter}-"))
        path = directory / f"{raw.adapter}.json"
        path.write_text(json.dumps({
            "source_kind": raw.source_kind,
            "adapter": raw.adapter,
            "transport_status": raw.transport_status,
            "execution_status": raw.execution_status,
            "payload": raw.payload,
        }, sort_keys=True), encoding="utf-8")
        return ArtifactSet((path,), raw.source_kind, raw.adapter)

    def release(self, lease: Lease) -> None:
        if lease.resource_key != self.resource_key:
            raise ValueError("lease does not belong to adapter resource")
        self._locks[self.resource_key].release()

    def run(self, spec: dict[str, Any]) -> ArtifactSet:
        lease = self.acquire(spec)
        try:
            raw = self.execute(lease, spec)
            return self.collect(raw)
        finally:
            self.release(lease)

    def _payload(self, spec: dict[str, Any]) -> dict[str, Any]:
        return {"job_id": spec["job_id"], "profile": spec.get("profile", "normal")}


class FixtureTrace32Adapter(FixtureAdapter):
    adapter_name = "trace32"

    def _payload(self, spec: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": spec["job_id"],
            "commands": spec.get("commands", ["SYStem.Mode Up"]),
            "registers": spec.get("registers", {"PC": "0x00000000"}),
            "target_halted": spec.get("target_halted", True),
        }


class FixtureAardvarkAdapter(FixtureAdapter):
    adapter_name = "aardvark"

    def _payload(self, spec: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": spec["job_id"],
            "bus": spec.get("bus", "I2C"),
            "address_or_cs": spec.get("address_or_cs", "0x50"),
            "read_bytes": spec.get("read_bytes", "aabbccdd"),
        }


class FixtureEdaAdapter(FixtureAdapter):
    adapter_name = "eda"

    def _payload(self, spec: dict[str, Any]) -> dict[str, Any]:
        return {
            "job_id": spec["job_id"],
            "tool_name": spec.get("tool_name", "synthetic-eda"),
            "flow_name": spec.get("flow_name", "timing"),
            "exit_code": spec.get("exit_code", 0),
            "report_names": spec.get("report_names", ["timing.report"]),
        }
