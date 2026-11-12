import sys
import types
from types import SimpleNamespace

import pytest

from agentor.runtime import BoxdRuntime, E2BCodeInterpreterRuntime, SmolVMRuntime
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


class FakeNotFoundError(Exception):
    pass


def install_fake_boxd(monkeypatch, status="running", ready_error=None):
    statuses = [status] if isinstance(status, str) else list(status)

    calls = {
        "client": None,
        "create": None,
        "start": [],
        "ready": [],
        "exec": [],
        "delete": [],
    }

    class FakeMachines:
        def create(self, **kwargs):
            calls["create"] = kwargs
            return SimpleNamespace(id="m-123", name="agentor-1")

        def wait_until_ready(self, machine_id):
            calls["ready"].append(machine_id)
            if ready_error is not None:
                raise ready_error

        def get(self, machine_id):
            current = statuses.pop(0) if len(statuses) > 1 else statuses[0]
            return SimpleNamespace(id=machine_id, status=current)

        def start(self, machine_id):
            calls["start"].append(machine_id)

        def exec(self, machine_id, command, **kwargs):
            calls["exec"].append((machine_id, command, kwargs))
            return SimpleNamespace(stdout="out\n", stderr="err\n", exit_code=1)

        def delete(self, machine_id):
            calls["delete"].append(machine_id)

    class FakeBoxd:
        def __init__(self, api_key=None, region=None):
            calls["client"] = {"api_key": api_key, "region": region}
            self.machines = FakeMachines()

    fake_module = types.ModuleType("boxd")
    fake_module.Boxd = FakeBoxd
    fake_module.NotFoundError = FakeNotFoundError
    monkeypatch.setitem(sys.modules, "boxd", fake_module)
    return calls


def test_boxd_runtime_creates_isolated_machine_runs_command_and_deletes(monkeypatch):
    calls = install_fake_boxd(monkeypatch)

    runtime = BoxdRuntime(timeout=15, api_key="key", region="fra", vcpu=2)
    request = ShellCommandRequest(
        command="echo $DEBUG | wc -c",
        working_directory="/tmp/boxd dir",
        env={"DEBUG": "1", "RETRIES": 3},
        timeout_ms=2500,
    )

    result = runtime(request)

    assert calls["client"] == {"api_key": "key", "region": "fra"}
    assert calls["create"] == {"isolated": True, "vcpu": 2}
    assert calls["ready"] == ["m-123"]
    assert calls["exec"] == [
        (
            "m-123",
            ["bash", "-c", "echo $DEBUG | wc -c"],
            {
                "env": {"DEBUG": "1", "RETRIES": "3"},
                "cwd": "/tmp/boxd dir",
                "timeout": 3,
            },
        )
    ]
    assert result == "out\nerr\n"

    runtime.close()
    runtime.close()
    assert calls["delete"] == ["m-123"]


def test_boxd_runtime_default_timeout_and_no_env(monkeypatch):
    calls = install_fake_boxd(monkeypatch)

    runtime = BoxdRuntime()
    runtime(ShellCommandRequest(command="ls"))

    assert calls["exec"][0][2] == {"env": None, "cwd": None, "timeout": 30}


def test_boxd_runtime_attaches_to_existing_machine_without_deleting(monkeypatch):
    calls = install_fake_boxd(monkeypatch, status="hibernated")

    runtime = BoxdRuntime(machine_id="m-existing")
    runtime(ShellCommandRequest(command="pwd"))
    runtime.close()

    assert calls["create"] is None
    assert calls["start"] == []
    assert calls["exec"][0][0] == "m-existing"
    assert calls["delete"] == []


def test_boxd_runtime_starts_a_stopped_machine(monkeypatch):
    monkeypatch.setattr("agentor.runtime.time.sleep", lambda seconds: None)
    calls = install_fake_boxd(
        monkeypatch, status=["stopped", "stopped", "starting", "running"]
    )

    BoxdRuntime(machine_id="m-stopped")

    assert calls["start"] == ["m-stopped"]
    assert calls["ready"] == ["m-stopped"]


def test_boxd_runtime_deletes_machine_that_never_gets_ready(monkeypatch):
    calls = install_fake_boxd(monkeypatch, ready_error=TimeoutError("not ready"))

    with pytest.raises(TimeoutError):
        BoxdRuntime()

    assert calls["delete"] == ["m-123"]


def test_boxd_runtime_close_ignores_machine_already_gone(monkeypatch):
    calls = install_fake_boxd(monkeypatch)
    runtime = BoxdRuntime()

    def gone(machine_id):
        calls["delete"].append(machine_id)
        raise FakeNotFoundError(machine_id)

    runtime.client.machines.delete = gone
    runtime.close()

    assert calls["delete"] == ["m-123"]
