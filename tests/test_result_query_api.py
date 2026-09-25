import json
import threading
import unittest
from urllib.request import urlopen

from eda_lab.api import ApiHandler, create_server
from eda_lab.service import JobService
from eda_lab.store import Store


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

    def test_new_violation_endpoint_enables_the_selected_query_index(self):
        with urlopen(f"http://127.0.0.1:{self.server.server_port}/revisions/candidate/new-violations?baseline=base") as response:
            payload = json.loads(response.read())
        self.assertEqual(payload["comparability"], "COMPARABLE")
        self.assertEqual(len(payload["findings"]), 1)
        self.assertTrue(self.store.has_finding_query_index())


if __name__ == "__main__":
    unittest.main()
