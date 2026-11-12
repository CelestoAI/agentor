import math
import shlex
import time

from agentor.tools.shell import ShellCommandRequest


class SandboxRuntime:
    """Base interface for sandbox-backed shell runtimes."""

    def __call__(self, request: ShellCommandRequest) -> str:
        raise NotImplementedError("SandboxRuntime is not implemented")


class E2BCodeInterpreterRuntime(SandboxRuntime):
    """Execute shell commands inside an E2B Code Interpreter sandbox."""

    def __init__(self, timeout: int | None = None):
        from e2b_code_interpreter import Sandbox

        self.sbx = Sandbox.create(timeout=timeout)

    def __call__(self, request: ShellCommandRequest) -> str:
        execution = self.sbx.run_code(request.command)
        return execution.logs


class SmolVMRuntime(SandboxRuntime):
    """Execute shell commands inside a SmolVM sandbox."""

    def __init__(
        self,
        timeout: int | None = None,
        start: bool = True,
        **smolvm_kwargs,
    ):
        from smolvm import SmolVM

        self.timeout = timeout
        self.vm = SmolVM(**smolvm_kwargs)

        if start:
            self.vm.start()

    def __call__(self, request: ShellCommandRequest) -> str:
        timeout_seconds = self.timeout or 30
        if request.timeout_ms is not None:
            timeout_seconds = max(1, math.ceil(request.timeout_ms / 1000))

        command = request.command
        if request.working_directory:
            command = f"cd {shlex.quote(request.working_directory)} && {command}"

        if request.env:
            env_vars = {key: str(value) for key, value in request.env.items()}
            self.vm.set_env_vars(env_vars)

        execution = self.vm.run(command, timeout=timeout_seconds)
        return execution.stdout + execution.stderr

    def close(self) -> None:
        """Best-effort cleanup for the underlying VM."""
        try:
            self.vm.stop()
        except Exception:
            pass

        try:
            self.vm.close()
        except Exception:
            pass


class BoxdRuntime(SandboxRuntime):
    """Execute shell commands inside a boxd machine (https://boxd.sh?ref=agentor).

    By default a new isolated machine is created and deleted again by
    `close()`. Pass `machine_id` to run commands in a machine you already
    have; `close()` leaves that one alone. Extra keyword arguments go to
    `machines.create` (for example `vcpu`, `memory`, `labels`, `from_snapshot`).
    The API key is read from `BOXD_API_KEY` unless `api_key` is given. Inside
    a boxd machine without a key, the boxd SDK uses that machine's own login.
    """

    def __init__(
        self,
        timeout: int | None = None,
        machine_id: str | None = None,
        api_key: str | None = None,
        region: str | None = None,
        isolated: bool = True,
        **create_kwargs,
    ):
        from boxd import Boxd

        self.timeout = timeout
        self.client = Boxd(api_key=api_key, region=region)
        self.owns_machine = machine_id is None

        if machine_id is None:
            machine = self.client.machines.create(isolated=isolated, **create_kwargs)
            self.machine_id = machine.id
            try:
                self.client.machines.wait_until_ready(self.machine_id)
            except BaseException:
                try:
                    self.close()
                except Exception:
                    pass
                raise
        else:
            self.machine_id = machine_id
            if self.client.machines.get(machine_id).status == "stopped":
                self.client.machines.start(machine_id)
                self._wait_until_started()
                self.client.machines.wait_until_ready(machine_id)

    def _wait_until_started(self, timeout: float = 90.0) -> None:
        deadline = time.monotonic() + timeout
        while self.client.machines.get(self.machine_id).status == "stopped":
            if time.monotonic() >= deadline:
                raise TimeoutError(f"machine {self.machine_id} did not start")
            time.sleep(0.5)

    def __call__(self, request: ShellCommandRequest) -> str:
        timeout_seconds = self.timeout or 30
        if request.timeout_ms is not None:
            timeout_seconds = max(1, math.ceil(request.timeout_ms / 1000))

        env = None
        if request.env:
            env = {key: str(value) for key, value in request.env.items()}

        execution = self.client.machines.exec(
            self.machine_id,
            ["bash", "-c", request.command],
            env=env,
            cwd=request.working_directory,
            timeout=timeout_seconds,
        )
        return execution.stdout + execution.stderr

    def close(self) -> None:
        """Delete the machine if this runtime created it."""
        from boxd import NotFoundError

        if not self.owns_machine:
            return
        try:
            self.client.machines.delete(self.machine_id)
        except NotFoundError:
            pass
        self.owns_machine = False
