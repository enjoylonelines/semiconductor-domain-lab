import base64
import json
import math
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from .models import JobSpec
from .service import BackpressureError, IdempotencyConflict, JobService


def service_from_environment() -> JobService:
    """Build the explicit PostgreSQL API role when EDA_POSTGRES_DSN is set."""
    dsn = os.environ.get("EDA_POSTGRES_DSN")
    if not dsn:
        return JobService()
    from .postgres_store import PostgresStore
    return JobService(PostgresStore(dsn), max_in_flight=int(os.environ.get("EDA_MAX_IN_FLIGHT", "8")), execution_mode="external", worker_id=os.environ.get("EDA_API_ID", "api"))


def _encode_cursor(run: dict) -> str:
    raw = json.dumps({"updated_at": run["updated_at"], "run_id": run["job_id"]}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _decode_cursor(value: str | None) -> tuple[float, str] | None:
    if not value:
        return None
    try:
        padded = value + "=" * (-len(value) % 4)
        raw = json.loads(base64.urlsafe_b64decode(padded))
        return float(raw["updated_at"]), str(raw["run_id"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise ValueError("invalid cursor") from exc


def _public_attempt(attempt: dict) -> dict:
    return {
        "attempt_no": attempt["attempt_no"],
        "status": attempt["status"],
        "retry_class": attempt.get("retry_class"),
        "error_type": attempt.get("error_type"),
        "error": attempt.get("error"),
        "started_at": attempt.get("started_at"),
        "updated_at": attempt.get("updated_at"),
    }


def _public_run(run: dict, *, include_attempts: bool) -> dict:
    payload = {
        "run_id": run["job_id"],
        "design": {"id": run["design_id"], "ip_family": run["ip_family"]},
        "flow": {"name": run["flow_name"]},
        "status": {
            "execution": run["status"], "parse": run["parse_status"], "check": run["check_status"],
            "completeness": run["completeness"], "semantic": run["semantic_status"],
            "provenance": run["provenance_status"], "trust": run["trust_status"],
        },
        "updated_at": run["updated_at"],
        "artifact": {"available": bool(run.get("artifact_path"))},
        "error": run.get("error"),
    }
    if include_attempts:
        payload["attempts"] = [_public_attempt(attempt) for attempt in run["attempts"]]
    return payload


class ApiHandler(BaseHTTPRequestHandler):
    service = JobService()

    def _send(self, status: int, payload: dict, headers: dict[str, str] | None = None) -> None:
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:
        if self.path != "/jobs":
            self._send(404, {"error": "not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            spec = JobSpec(job_id=data["job_id"], design_id=data["design_id"], ip_family=data["ip_family"], flow_name=data.get("flow_name", "synthetic-timing"), corner=data.get("corner", "TT_25C"), worst_slack=float(data.get("worst_slack", 0.12)), unit=data.get("unit", "ns"), duration_seconds=float(data.get("duration_seconds", 0.02)))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        try:
            self._send(202, self.service.submit(spec))
        except BackpressureError as exc:
            self._send(429, {"error": "in_flight_budget_exhausted", "retryable": True, "retry_after_ms": round(exc.retry_after_seconds * 1000)}, {"Retry-After": str(max(1, math.ceil(exc.retry_after_seconds)))})
        except IdempotencyConflict:
            self._send(409, {"error": "idempotency_key_reused_with_different_spec", "retryable": False})

    def _list_runs(self, query: dict[str, list[str]]) -> None:
        try:
            limit = int(query.get("limit", ["25"])[0])
            if not 1 <= limit <= 100:
                raise ValueError("limit must be between 1 and 100")
            cursor = _decode_cursor(query.get("cursor", [None])[0])
        except ValueError as exc:
            self._send(400, {"error": str(exc)})
            return
        status = query.get("status", [None])[0]
        rows = self.service.store.list_runs(status=status, limit=limit + 1, cursor=cursor)
        page, remaining = rows[:limit], rows[limit:]
        self._send(200, {"items": [_public_run(run, include_attempts=False) for run in page], "next_cursor": _encode_cursor(page[-1]) if remaining and page else None})

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        query = parse_qs(request.query)
        if request.path == "/runs":
            self._list_runs(query)
            return
        run_prefix = "/runs/"
        if request.path.startswith(run_prefix):
            run_id = request.path[len(run_prefix):]
            if not run_id or "/" in run_id:
                self._send(404, {"error": "not found"})
                return
            result = self.service.get(run_id)
            self._send(200, _public_run(result, include_attempts=True)) if result else self._send(404, {"error": "run not found"})
            return
        revision_prefix, revision_suffix = "/revisions/", "/new-violations"
        if request.path.startswith(revision_prefix) and request.path.endswith(revision_suffix):
            candidate = request.path[len(revision_prefix):-len(revision_suffix)]
            baseline = query.get("baseline", [None])[0]
            if not candidate or not baseline:
                self._send(400, {"error": "baseline query parameter is required"})
                return
            try:
                if self.service.enable_new_violation_index:
                    self.service.store.create_finding_query_index()
                self._send(200, self.service.store.new_violations(baseline, candidate))
            except KeyError as exc:
                self._send(404, {"error": str(exc)})
            return
        prefix = "/jobs/"
        if request.path.startswith(prefix):
            job_id = request.path[len(prefix):]
            result = self.service.get(job_id)
            self._send(200, result) if result else self._send(404, {"error": "job not found"})
            return
        self._send(404, {"error": "not found"})

    def log_message(self, format: str, *args) -> None:
        return


def create_server(host: str = "127.0.0.1", port: int = 8080, service: JobService | None = None) -> ThreadingHTTPServer:
    if service is None:
        return ThreadingHTTPServer((host, port), ApiHandler)
    handler = type("ConfiguredApiHandler", (ApiHandler,), {"service": service})
    return ThreadingHTTPServer((host, port), handler)
