import json
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from eda_lab.api import ApiHandler, create_server
from eda_lab.service import JobService
from eda_lab.store import Store


class RunsApiTests(unittest.TestCase):
    def setUp(self):
        self.clock = [100.0]
        self.store = Store(now=lambda: self.clock[0])
        for job_id, status, updated_at in (("run-c", "SUCCEEDED", 300.0), ("run-b", "RUNNING", 200.0), ("run-a", "FAILED", 100.0)):
            self.clock[0] = updated_at
            self.store.create_run(job_id, "design-a", "UART", "timing")
            self.store.update_run(job_id, status=status, artifact_path=f"/private/{job_id}.rpt")
        self.store.record_attempt("run-c", 1, "SUCCEEDED", retry_class="not_applicable")
        self.store.acquire_attempt_lease("run-c", 1, "worker-private", "secret-lease-token", 30)
        self.initial_service = ApiHandler.service
        ApiHandler.service = JobService(self.store)
        self.server = create_server(port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        ApiHandler.service.close()
        ApiHandler.service = self.initial_service

    def read(self, path):
        with urlopen(f"http://127.0.0.1:{self.server.server_port}{path}") as response:
            return response.status, json.loads(response.read())

    def test_lists_newest_runs_with_a_stable_cursor(self):
        status, first = self.read("/runs?limit=2")
        self.assertEqual(status, 200)
        self.assertEqual([item["run_id"] for item in first["items"]], ["run-c", "run-b"])
        self.assertIsNotNone(first["next_cursor"])
        _, second = self.read(f"/runs?limit=2&cursor={first['next_cursor']}")
        self.assertEqual([item["run_id"] for item in second["items"]], ["run-a"])
        self.assertIsNone(second["next_cursor"])

    def test_filters_by_execution_status(self):
        _, payload = self.read("/runs?status=RUNNING")
        self.assertEqual([item["run_id"] for item in payload["items"]], ["run-b"])

    def test_detail_hides_store_and_lease_secrets(self):
        _, payload = self.read("/runs/run-c")
        self.assertEqual(payload["run_id"], "run-c")
        self.assertTrue(payload["artifact"]["available"])
        self.assertEqual(payload["attempts"][0]["attempt_no"], 1)
        encoded = json.dumps(payload)
        self.assertNotIn("secret-lease-token", encoded)
        self.assertNotIn("worker-private", encoded)
        self.assertNotIn("/private/run-c.rpt", encoded)
        self.assertNotIn("lease_token", encoded)
        self.assertNotIn("artifact_path", encoded)

    def test_rejects_an_invalid_cursor(self):
        with self.assertRaises(HTTPError) as raised:
            self.read("/runs?cursor=not-a-cursor")
        response = raised.exception
        try:
            self.assertEqual(response.code, 400)
            self.assertEqual(json.loads(response.read())["error"], "invalid cursor")
        finally:
            response.close()


if __name__ == "__main__":
    unittest.main()
