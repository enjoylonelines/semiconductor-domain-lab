import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from eda_lab.api import ApiHandler, create_server
from eda_lab.service import JobService
from eda_lab.store import Store


class BlockingAdapter:
    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()

    def run(self, spec):
        self.started.set()
        self.release.wait(timeout=2)
        from eda_lab.runner import SyntheticTimingAdapter
        return SyntheticTimingAdapter().run(spec)


class ResultQueryApiTests(unittest.TestCase):
    def setUp(self):
        store = Store()
        store.create_revision("base", "design-a", "a", "lib", "sdc", "OpenSTA-3.1", "parser-1")
        store.create_revision("candidate", "design-a", "b", "lib", "sdc", "OpenSTA-3.1", "parser-1")
        store.save_findings("candidate", [("run", "A/Q", "B/D", "clk", "setup", "TT", -0.1)])
        ApiHandler.service = JobService(store)
        self.store = store
        self.server = create_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def test_new_violation_endpoint_does_not_change_storage_policy_by_default(self):
        with urlopen(f"http://127.0.0.1:{self.server.server_port}/revisions/candidate/new-violations?baseline=base") as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["comparability"], "COMPARABLE")
        self.assertEqual(len(payload["findings"]), 1)
        self.assertFalse(self.store.has_finding_query_index())

    def test_explicit_operational_setting_enables_the_query_index(self):
        ApiHandler.service = JobService(self.store, enable_new_violation_index=True)
        with urlopen(f"http://127.0.0.1:{self.server.server_port}/revisions/candidate/new-violations?baseline=base") as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["comparability"], "COMPARABLE")
        self.assertTrue(self.store.has_finding_query_index())

    def test_backpressure_returns_retry_hint_without_creating_a_run(self):
        adapter = BlockingAdapter()
        ApiHandler.service = JobService(
            Store(), max_workers=1, max_attempts=1, adapter=adapter,
            max_in_flight=1, backpressure_retry_after_seconds=0.3,
        )
        payload = {
            "job_id": "first", "design_id": "d", "ip_family": "ip",
            "flow_name": "timing", "corner": "TT", "worst_slack": 0.1, "unit": "ns",
        }
        self._post(payload)
        self.assertTrue(adapter.started.wait(timeout=1))
        payload["job_id"] = "retry-later"
        with self.assertRaises(HTTPError) as raised:
            self._post(payload)
        response = raised.exception
        self.assertEqual(response.code, 429)
        self.assertEqual(response.headers["Retry-After"], "1")
        try:
            self.assertEqual(json.loads(response.read()), {
                "error": "in_flight_budget_exhausted", "retry_after_ms": 300, "retryable": True,
            })
        finally:
            response.close()
        self.assertIsNone(ApiHandler.service.get("retry-later"))
        adapter.release.set()
        ApiHandler.service.futures["first"].result(timeout=2)
        self.assertEqual(self._post(payload)[0], 202)

    def _post(self, payload):
        request = Request(
            f"http://127.0.0.1:{self.server.server_port}/jobs", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with urlopen(request, timeout=2) as response:
            return response.status, json.loads(response.read())


if __name__ == "__main__":
    unittest.main()
