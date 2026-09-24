import json
import unittest

from eda_lab.adapters import (
    FixtureAardvarkAdapter,
    FixtureEdaAdapter,
    FixtureTrace32Adapter,
)


class AdapterContractTests(unittest.TestCase):
    def test_all_fixture_adapters_follow_lifecycle_and_mark_provenance(self):
        adapters = [FixtureTrace32Adapter("t32-contract"), FixtureAardvarkAdapter("aa-contract"), FixtureEdaAdapter("eda-contract")]
        for adapter in adapters:
            artifacts = adapter.run({"job_id": f"job-{adapter.adapter_name}"})
            self.assertEqual(artifacts.source_kind, "fixture")
            self.assertEqual(artifacts.adapter, adapter.adapter_name)
            payload = json.loads(artifacts.paths[0].read_text(encoding="utf-8"))
            self.assertEqual(payload["source_kind"], "fixture")
            self.assertEqual(payload["execution_status"], "SUCCEEDED")

    def test_resource_is_exclusive_and_release_allows_next_owner(self):
        adapter = FixtureTrace32Adapter("t32-exclusive")
        lease = adapter.acquire({"job_id": "first"})
        with self.assertRaisesRegex(RuntimeError, "resource_unavailable"):
            adapter.acquire({"job_id": "second"})
        adapter.release(lease)
        next_lease = adapter.acquire({"job_id": "second"})
        adapter.release(next_lease)

    def test_timeout_releases_resource(self):
        adapter = FixtureAardvarkAdapter("aa-timeout")
        with self.assertRaises(TimeoutError):
            adapter.run({"job_id": "timeout", "profile": "timeout"})
        artifacts = adapter.run({"job_id": "after-timeout"})
        self.assertEqual(artifacts.source_kind, "fixture")


if __name__ == "__main__":
    unittest.main()
