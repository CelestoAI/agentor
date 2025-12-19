from agentor.tools.shell import ShellCommandRequest


class SandboxRuntime:
    def __call__(self, code: str) -> str:
        raise NotImplementedError("SandboxRuntime is not implemented")


class E2BCodeInterpreterRuntime(SandboxRuntime):
    def __init__(self, timeout: int | None = None):
        from e2b_code_interpreter import Sandbox

        self.sbx = Sandbox.create(timeout=timeout)

    def __call__(self, request: ShellCommandRequest) -> str:
        execution = self.sbx.run_code(request.command)
        return execution.logs
