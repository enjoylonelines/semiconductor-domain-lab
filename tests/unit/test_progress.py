import json
import unittest

from eda_lab.models import JobSpec
from eda_lab.progress import RedisProgressPublisher
from eda_lab.runner import SyntheticTimingAdapter
from eda_lab.service import JobService
from eda_lab.store import Store


class RecordingClient:
    def __init__(self):
        self.calls = []

    def publish(self, channel, payload):
        self.calls.append((channel, payload))
        return 1


class FailingClient:
    def publish(self, channel, payload):
        raise ConnectionError("redis unavailable")


class RedisProgressPublisherTests(unittest.TestCase):
    def test_publish_serializes_ephemeral_progress_event(self):
        client = RecordingClient()
        publisher = RedisProgressPublisher(client, channel="progress", now=lambda: 123.5)

        self.assertTrue(publisher.publish("job-1", "RUNNING", attempt_no=2))

        channel, raw = client.calls[0]
        self.assertEqual(channel, "progress")
        self.assertEqual(
            json.loads(raw),
            {
                "attempt_no": 2,
                "job_id": "job-1",
                "observed_at": 123.5,
                "status": "RUNNING",
            },
        )

    def test_publish_failure_is_best_effort(self):
        publisher = RedisProgressPublisher(FailingClient())

        self.assertFalse(publisher.publish("job-1", "SUCCEEDED"))

    def test_redis_failure_does_not_fail_execution(self):
        publisher = RedisProgressPublisher(FailingClient())
        service = JobService(
            Store(),
            max_workers=1,
            max_attempts=1,
            adapter=SyntheticTimingAdapter(),
            execution_mode="local",
            progress_publisher=publisher,
        )
        try:
            spec = JobSpec("redis-down-job", "d", "ip", "timing", "TT", 0.1, "ns")
            service.submit(spec)
            service.futures[spec.job_id].result(timeout=2)
            self.assertEqual(service.get(spec.job_id)["status"], "SUCCEEDED")
        finally:
            service.close()


if __name__ == "__main__":
    unittest.main()
