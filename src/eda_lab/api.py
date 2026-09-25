import json
import math
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from .models import JobSpec
from .service import BackpressureError, JobService

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
            spec = JobSpec(
                job_id=data["job_id"], design_id=data["design_id"],
                ip_family=data["ip_family"], flow_name=data.get("flow_name", "synthetic-timing"),
                corner=data.get("corner", "TT_25C"), worst_slack=float(data.get("worst_slack", 0.12)),
                unit=data.get("unit", "ns"), duration_seconds=float(data.get("duration_seconds", 0.02)),
            )
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send(400, {"error": str(exc)})
            return
        try:
            self._send(202, self.service.submit(spec))
        except BackpressureError as exc:
            self._send(429, {
                "error": "in_flight_budget_exhausted",
                "retryable": True,
                "retry_after_ms": round(exc.retry_after_seconds * 1000),
            }, {"Retry-After": str(max(1, math.ceil(exc.retry_after_seconds)))})

    def do_GET(self) -> None:
        request = urlsplit(self.path)
        revision_prefix = "/revisions/"
        revision_suffix = "/new-violations"
        if request.path.startswith(revision_prefix) and request.path.endswith(revision_suffix):
            candidate = request.path[len(revision_prefix):-len(revision_suffix)]
            baseline = parse_qs(request.query).get("baseline", [None])[0]
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
        if not request.path.startswith(prefix):
            self._send(404, {"error": "not found"})
            return
        job_id = request.path[len(prefix):]
        result = self.service.get(job_id)
        self._send(200, result) if result else self._send(404, {"error": "job not found"})

    def log_message(self, format: str, *args) -> None:
        return

def create_server(host: str = "127.0.0.1", port: int = 8080) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ApiHandler)
