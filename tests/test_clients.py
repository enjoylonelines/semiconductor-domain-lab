import subprocess
import unittest

from eda_lab.clients import (
    AardvarkClientConfig,
    AardvarkModuleClient,
    Trace32ClientConfig,
    Trace32SubprocessClient,
)


class Completed:
    returncode = 0
    stdout = "OK"
    stderr = ""


class FakeAardvarkModule:
    def __init__(self):
        self.calls = []
    def open(self, device_id): self.calls.append(("open", device_id)); return "handle"
    def transfer(self, handle, transaction): self.calls.append(("transfer", handle, transaction)); return b"\\xaa"
    def close(self, handle): self.calls.append(("close", handle))


class ClientWrapperTests(unittest.TestCase):
    def test_trace32_subprocess_wrapper_builds_explicit_command(self):
        calls = []
        def runner(args, **kwargs):
            calls.append((args, kwargs))
            return Completed()
        client = Trace32SubprocessClient(Trace32ClientConfig(endpoint="127.0.0.1:20000"), runner=runner)
        client.connect()
        self.assertEqual(client.command("Data.List"), "OK")
        self.assertEqual(calls[0][0], ["t32rem", "-p", "127.0.0.1:20000", "Data.List"])
        client.close()

    def test_trace32_missing_executable_is_normalized(self):
        def runner(*args, **kwargs):
            raise FileNotFoundError("missing")
        client = Trace32SubprocessClient(Trace32ClientConfig(), runner=runner)
        client.connect()
        with self.assertRaisesRegex(RuntimeError, "configuration_error"):
            client.command("Data.List")

    def test_aardvark_module_wrapper_maps_open_transfer_close(self):
        module = FakeAardvarkModule()
        client = AardvarkModuleClient(AardvarkClientConfig(), module=module)
        client.open(3)
        self.assertEqual(client.transfer({"bus": "I2C", "address": "0x50"}), b"\\xaa")
        client.close()
        self.assertEqual(module.calls, [("open", 3), ("transfer", "handle", {"bus": "I2C", "address": "0x50"}), ("close", "handle")])

    def test_aardvark_missing_binding_is_normalized(self):
        client = AardvarkModuleClient(AardvarkClientConfig(module_name="module_that_is_not_installed"))
        with self.assertRaisesRegex(RuntimeError, "configuration_error"):
            client.open()


if __name__ == "__main__":
    unittest.main()
