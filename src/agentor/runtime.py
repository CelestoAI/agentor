import math
import shlex

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
