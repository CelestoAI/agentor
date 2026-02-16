import sys
import types
from types import SimpleNamespace

from agentor.runtime import E2BCodeInterpreterRuntime, SmolVMRuntime
from agentor.tools.shell import ShellCommandRequest


def test_e2b_runtime_executes_command(monkeypatch):
    calls: dict[str, object] = {}

    class FakeSandbox:
        @classmethod
        def create(cls, timeout=None):
            calls["timeout"] = timeout
            return cls()

        def run_code(self, command: str):
            calls["command"] = command
            return SimpleNamespace(logs=f"logs:{command}")

    fake_module = types.ModuleType("e2b_code_interpreter")
    fake_module.Sandbox = FakeSandbox
    monkeypatch.setitem(sys.modules, "e2b_code_interpreter", fake_module)

    runtime = E2BCodeInterpreterRuntime(timeout=42)
    result = runtime(ShellCommandRequest(command="echo hello"))

    assert calls["timeout"] == 42
    assert calls["command"] == "echo hello"
    assert result == "logs:echo hello"


def test_smolvm_runtime_executes_command_and_cleans_up(monkeypatch):
    calls = {
        "init_kwargs": None,
        "start": 0,
        "run": None,
        "set_env_vars": None,
        "stop": 0,
        "close": 0,
    }

    class FakeSmolVM:
        def __init__(self, **kwargs):
            calls["init_kwargs"] = kwargs

        def start(self):
            calls["start"] += 1

        def set_env_vars(self, env_vars: dict[str, str]):
            calls["set_env_vars"] = env_vars

        def run(self, command: str, timeout: int = 30):
            calls["run"] = (command, timeout)
            return SimpleNamespace(stdout="ok\n", stderr="")

        def stop(self):
            calls["stop"] += 1

        def close(self):
            calls["close"] += 1

    fake_module = types.ModuleType("smolvm")
    fake_module.SmolVM = FakeSmolVM
    monkeypatch.setitem(sys.modules, "smolvm", fake_module)

    runtime = SmolVMRuntime(timeout=15, mem_size_mib=1024)
    request = ShellCommandRequest(
        command="ls -la",
        working_directory="/tmp/smol vm",
        env={"DEBUG": "1", "RETRIES": 3},
        timeout_ms=2500,
    )

    result = runtime(request)

    assert calls["init_kwargs"] == {"mem_size_mib": 1024}
    assert calls["start"] == 1
    assert calls["set_env_vars"] == {"DEBUG": "1", "RETRIES": "3"}
    assert calls["run"] == ("cd '/tmp/smol vm' && ls -la", 3)
    assert result == "ok\n"

    runtime.close()
    assert calls["stop"] == 1
    assert calls["close"] == 1
