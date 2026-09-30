import json
import os
import time
import unittest
from uuid import uuid4

import redis

from eda_lab.models import JobSpec
from eda_lab.postgres_store import PostgresStore
from eda_lab.progress import RedisProgressPublisher
from eda_lab.runner import SyntheticTimingAdapter
from eda_lab.service import JobService


POSTGRES_DSN = os.environ.get("EDA_POSTGRES_TEST_DSN")
REDIS_URL = os.environ.get("EDA_REDIS_TEST_URL")


@unittest.skipUnless(POSTGRES_DSN and REDIS_URL, "set EDA_POSTGRES_TEST_DSN and EDA_REDIS_TEST_URL")
class RedisProgressIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.prefix = uuid4().hex
        self.store = PostgresStore(POSTGRES_DSN)
        self.redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
        self.publisher = RedisProgressPublisher(self.redis, channel=f"eda:test:{self.prefix}")
        self.service = JobService(
            self.store,
            max_workers=1,
            max_attempts=1,
            adapter=SyntheticTimingAdapter(),
            worker_id="redis-progress-test",
            execution_mode="local",
            progress_publisher=self.publisher,
        )

    def tearDown(self):
        self.service.close()
        self.redis.close()

    def spec(self, suffix):
        return JobSpec(f"{self.prefix}-{suffix}", "d", "ip", "timing", "TT", 0.1, "ns")

    def wait_terminal(self, job_id, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            run = self.store.get_run(job_id)
            if run and run["status"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return run
            time.sleep(0.01)
        self.fail(f"{job_id} did not reach terminal state")

    def test_live_events_are_ephemeral_and_postgres_recovers_current_state(self):
        pubsub = self.redis.pubsub()
        pubsub.subscribe(self.publisher.channel)
        # consume subscribe acknowledgement
        pubsub.get_message(timeout=1)

        first = self.spec("live-subscriber")
        self.service.submit(first)
        terminal = self.wait_terminal(first.job_id)
        self.assertEqual(terminal["status"], "SUCCEEDED")

        statuses = []
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and {"RUNNING", "SUCCEEDED"} - set(statuses):
            message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
            if message and message["type"] == "message":
                statuses.append(json.loads(message["data"])["status"])
        self.assertIn("RUNNING", statuses)
        self.assertIn("SUCCEEDED", statuses)
        pubsub.close()

        # No subscriber is connected for the second Run. Pub/Sub retention is
        # intentionally absent, yet execution correctness must not change.
        second = self.spec("no-subscriber")
        self.service.submit(second)
        terminal = self.wait_terminal(second.job_id)
        self.assertEqual(terminal["status"], "SUCCEEDED")

        # A reconnecting client recovers authoritative current state from
        # PostgreSQL rather than expecting Redis replay.
        recovered = self.store.get_run(second.job_id)
        self.assertEqual(recovered["status"], "SUCCEEDED")
        self.assertEqual(recovered["attempts"][-1]["status"], "SUCCEEDED")


if __name__ == "__main__":
    unittest.main()
