import os
import json
import threading
import unittest
from pathlib import Path
from uuid import uuid4

from eda_lab.models import JobSpec
from eda_lab.api import create_server
from eda_lab.postgres_store import PostgresStore
from eda_lab.runner import OpenStaSubprocessAdapter, SyntheticTimingAdapter
from eda_lab.service import BackpressureError, JobService
from eda_lab.worker import PostgresWorker


DSN = os.environ.get("EDA_POSTGRES_TEST_DSN")


@unittest.skipUnless(DSN, "set EDA_POSTGRES_TEST_DSN for a dedicated disposable PostgreSQL database")
class PostgresOperationalPathTests(unittest.TestCase):
    fixture_dir = Path(__file__).parents[2] / "docs/evidence/2026-09-24-real-sta"
    sta_path = Path("/tmp/eda-opensta-20260924/build/sta")
    liberty_path = Path("/tmp/eda-opensta-20260924/examples/sky130hd_tt.lib.gz")
    def setUp(self):
        self.prefix = uuid4().hex
        self.stores = []
        self.services = []

    def tearDown(self):
        for service in self.services:
            service.close()
        for store in self.stores:
            store.close()

    def store(self):
        store = PostgresStore(DSN)
        self.stores.append(store)
        return store

    def service(self, store, worker_id):
        service = JobService(store, max_workers=1, max_attempts=1, adapter=SyntheticTimingAdapter(),
                             worker_id=worker_id, max_in_flight=8, execution_mode="external")
        self.services.append(service)
        return service

    def spec(self, suffix):
        return JobSpec(f"{self.prefix}-{suffix}", "d", "ip", "timing", "TT", 0.1, "ns")

    def test_api_submit_is_queued_then_a_distinct_worker_claims_and_executes(self):
        api_store = self.store()
        api = self.service(api_store, "api-1")
        spec = self.spec("queued")
        self.assertEqual(api.submit(spec)["status"], "QUEUED")

        worker_store = self.store()
        worker_service = self.service(worker_store, "worker-1")
        self.assertEqual(PostgresWorker(worker_store, worker_service).drain(), [spec.job_id])
        completed = api.get(spec.job_id)
        self.assertEqual(completed["status"], "SUCCEEDED")
        self.assertEqual(completed["attempts"][-1]["lease_owner"], "worker-1")

    def test_http_api_writes_a_queued_postgres_run_for_a_distinct_worker(self):
        api = self.service(self.store(), "api-http")
        server = create_server(port=0, service=api)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        spec = self.spec("http")
        try:
            from urllib.request import Request, urlopen
            request = Request(
                f"http://127.0.0.1:{server.server_port}/jobs",
                data=json.dumps({"job_id": spec.job_id, "design_id": spec.design_id, "ip_family": spec.ip_family}).encode(),
                headers={"Content-Type": "application/json"}, method="POST",
            )
            with urlopen(request, timeout=2) as response:
                self.assertEqual(response.status, 202)
                self.assertEqual(json.loads(response.read())["status"], "QUEUED")
        finally:
            server.shutdown()
            server.server_close()
        worker_store = self.store()
        worker_service = self.service(worker_store, "worker-http")
        self.assertEqual(PostgresWorker(worker_store, worker_service).drain(), [spec.job_id])
        self.assertEqual(api.get(spec.job_id)["status"], "SUCCEEDED")

    @unittest.skipUnless(sta_path.is_file() and liberty_path.is_file(), "OpenSTA integration fixture is unavailable")
    def test_distinct_postgres_worker_persists_a_real_opensta_result(self):
        api = self.service(self.store(), "api-1")
        spec = self.spec("real-opensta")
        api.submit(spec)
        adapter = OpenStaSubprocessAdapter(
            sta_path=self.sta_path, liberty_path=self.liberty_path, fixture_dir=self.fixture_dir, timeout_seconds=2,
        )
        worker_store = self.store()
        worker_service = JobService(worker_store, max_workers=1, max_attempts=1, adapter=adapter,
                                    worker_id="worker-real", max_in_flight=8, execution_mode="external")
        self.services.append(worker_service)
        self.assertEqual(PostgresWorker(worker_store, worker_service).drain(), [spec.job_id])
        result = api.get(spec.job_id)
        self.assertEqual(result["status"], "SUCCEEDED")
        self.assertEqual(result["trust_status"], "TRUSTED")
        self.assertEqual(result["attempts"][-1]["lease_owner"], "worker-real")

    def test_two_workers_atomically_claim_only_one_queued_run(self):
        api = self.service(self.store(), "api-1")
        spec = self.spec("one-claim")
        api.submit(spec)
        workers = [self.store(), self.store()]
        barrier = threading.Barrier(2)
        claims = []

        def claim(store):
            barrier.wait(timeout=2)
            claims.append(store.claim_next_run("worker"))

        threads = [threading.Thread(target=claim, args=(store,)) for store in workers]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=3)
        self.assertEqual(sum(claim is not None for claim in claims), 1)
        self.assertEqual(api.get(spec.job_id)["status"], "RUNNING")
        api.store.update_run(spec.job_id, status="FAILED", error="test cleanup after claim assertion")

    def test_z_shared_admission_budget_rejects_the_ninth_unique_run_without_persisting_it(self):
        services = [self.service(self.store(), "api-1"), self.service(self.store(), "api-2")]
        for index in range(8):
            services[index % 2].submit(self.spec(f"budget-{index}"))
        ninth = self.spec("budget-9")
        with self.assertRaises(BackpressureError):
            services[0].submit(ninth)
        self.assertIsNone(services[1].get(ninth.job_id))
        for index in range(8):
            services[index % 2].store.update_run(self.spec(f"budget-{index}").job_id, status="FAILED", error="test cleanup")


if __name__ == "__main__":
    unittest.main()
