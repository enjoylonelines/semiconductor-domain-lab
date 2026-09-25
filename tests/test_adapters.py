import json
import unittest

from eda_lab.adapters import (
    FixtureAardvarkAdapter,
    FixtureEdaAdapter,
    FixtureTrace32Adapter,
    RealAardvarkAdapter,
    RealTrace32Adapter,
)


class FakeTrace32Client:
    def __init__(self):
        self.calls = []
    def connect(self, endpoint): self.calls.append(("connect", endpoint))
    def command(self, command): self.calls.append(("command", command)); return "OK"
    def close(self): self.calls.append(("close",))


class FakeAardvarkClient:
    def __init__(self):
        self.calls = []
    def open(self, device_id): self.calls.append(("open", device_id))
    def transfer(self, transaction): self.calls.append(("transfer", transaction)); return "aabb"
    def close(self): self.calls.append(("close",))


class FailingAardvarkClient(FakeAardvarkClient):
    def transfer(self, transaction):
        self.calls.append(("transfer", transaction))
        raise ConnectionError("synthetic bus disconnect")


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

    def test_injected_real_clients_map_calls_and_mark_real_source(self):
        trace_client = FakeTrace32Client()
        trace = RealTrace32Adapter(trace_client, "t32-real-contract")
        trace_artifact = trace.run({"job_id": "t32", "endpoint": "127.0.0.1", "commands": ["Data.List"]})
        self.assertEqual(trace_artifact.source_kind, "real")
        self.assertEqual(trace_client.calls, [("connect", "127.0.0.1"), ("command", "Data.List"), ("close",)])

        aardvark_client = FakeAardvarkClient()
        aardvark = RealAardvarkAdapter(aardvark_client, "aa-real-contract")
        aardvark_artifact = aardvark.run({"job_id": "aa", "device_id": 3, "transactions": [{"bus": "I2C", "address": "0x50"}]})
        self.assertEqual(aardvark_artifact.source_kind, "real")
        self.assertEqual(aardvark_client.calls[0], ("open", 3))
        self.assertEqual(aardvark_client.calls[-1], ("close",))

    def test_real_adapter_without_client_fails_explicitly(self):
        with self.assertRaisesRegex(RuntimeError, "configuration_error"):
            RealTrace32Adapter().run({"job_id": "missing"})

    def test_timeout_releases_resource(self):
        adapter = FixtureAardvarkAdapter("aa-timeout")
        with self.assertRaises(TimeoutError):
            adapter.run({"job_id": "timeout", "profile": "timeout"})
        artifacts = adapter.run({"job_id": "after-timeout"})
        self.assertEqual(artifacts.source_kind, "fixture")

    def test_unknown_destructive_hardware_outcome_quarantines_until_operator_clears_it(self):
        client = FailingAardvarkClient()
        adapter = RealAardvarkAdapter(client, "aa-unknown-outcome")
        spec = {
            "job_id": "flash-attempt",
            "device_id": 3,
            "operation_kind": "destructive",
            "transactions": [{"write": "firmware"}],
        }
        with self.assertRaises(ConnectionError):
            adapter.run(spec)

        with self.assertRaisesRegex(RuntimeError, "resource_quarantined: unknown_hardware_state"):
            adapter.acquire({"job_id": "next-attempt"})

        adapter.clear_quarantine(operator_id="lab-operator", inspection_id="board-reset-42")
        lease = adapter.acquire({"job_id": "after-inspection", "device_id": 3})
        adapter.release(lease)

    def test_read_only_transport_error_does_not_imply_destructive_unknown_state(self):
        client = FailingAardvarkClient()
        adapter = RealAardvarkAdapter(client, "aa-read-only-error")
        with self.assertRaises(ConnectionError):
            adapter.run({
                "job_id": "read-attempt",
                "device_id": 3,
                "operation_kind": "read_only",
                "transactions": [{"read": 4}],
            })
        lease = adapter.acquire({"job_id": "retry-after-transport", "device_id": 3})
        adapter.release(lease)


if __name__ == "__main__":
    unittest.main()
