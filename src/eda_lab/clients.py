from __future__ import annotations

import importlib
import subprocess
from dataclasses import dataclass
from typing import Any, Callable


@dataclass(frozen=True)
class Trace32ClientConfig:
    executable: str = "t32rem"
    endpoint: str | None = None
    timeout_seconds: float = 10.0


class Trace32SubprocessClient:
    """Software client for t32rem; it executes only an explicitly configured command."""

    def __init__(self, config: Trace32ClientConfig, runner: Callable[..., Any] | None = None):
        self.config = config
        self.runner = runner or subprocess.run
        self.connected = False

    def connect(self, endpoint: str | None = None) -> None:
        self.config = Trace32ClientConfig(self.config.executable, endpoint or self.config.endpoint, self.config.timeout_seconds)
        self.connected = True

    def command(self, command: str) -> str:
        if not self.connected:
            raise RuntimeError("configuration_error: TRACE32 client is not connected")
        args = [self.config.executable]
        if self.config.endpoint:
            args.extend(["-p", self.config.endpoint])
        args.append(command)
        try:
            completed = self.runner(args, check=False, capture_output=True, text=True, timeout=self.config.timeout_seconds)
        except FileNotFoundError as exc:
            raise RuntimeError("configuration_error: t32rem executable not found") from exc
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError("TRACE32 command timeout") from exc
        if completed.returncode != 0:
            raise ConnectionError(f"TRACE32 command failed: {completed.stderr.strip()}")
        return completed.stdout

    def close(self) -> None:
        self.connected = False


@dataclass(frozen=True)
class AardvarkClientConfig:
    module_name: str = "aardvark_py"
    device_id: int = 0


class AardvarkModuleClient:
    """Software client for an installed Total Phase Python binding."""

    def __init__(self, config: AardvarkClientConfig, module: Any | None = None):
        self.config = config
        self.module = module
        self.handle = None

    def open(self, device_id: int | None = None) -> None:
        if self.module is None:
            try:
                self.module = importlib.import_module(self.config.module_name)
            except ImportError as exc:
                raise RuntimeError("configuration_error: Aardvark Python binding not installed") from exc
        try:
            self.handle = self.module.open(device_id if device_id is not None else self.config.device_id)
        except Exception as exc:
            raise ConnectionError(f"Aardvark open failed: {exc}") from exc

    def transfer(self, transaction: dict[str, Any]) -> Any:
        if self.handle is None:
            raise RuntimeError("configuration_error: Aardvark client is not open")
        try:
            return self.module.transfer(self.handle, transaction)
        except TimeoutError:
            raise
        except Exception as exc:
            raise ConnectionError(f"Aardvark transfer failed: {exc}") from exc

    def close(self) -> None:
        if self.module is not None and self.handle is not None:
            self.module.close(self.handle)
        self.handle = None
