import os
import shlex
import subprocess
from typing import Callable

from pydantic import BaseModel

from agentor.tools import BaseTool, capability


class ShellCommandRequest(BaseModel):
    command: str
    working_directory: str | None = None
    env: dict | None = None
    timeout_ms: int | None = None


class ShellTool(BaseTool):
    name = "shell_tool"
    description = "Execute shell commands"

    def __init__(
        self,
        executor: Callable[[ShellCommandRequest], str] = None,
        verbose: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.executor = executor or _shell_executor
        self.verbose = verbose

    @capability
    def run(self, request: ShellCommandRequest):
        if self.verbose:
            print(
                f"Running command: {request.command} in working directory: {request.working_directory or os.getcwd()}"
            )
        result = self.executor(request)
        if self.verbose:
            print(f"Command result: {result}")
        return result


def _shell_executor(request: ShellCommandRequest) -> str:
    args = request

    try:
        # Properly split the command for subprocess.run to avoid FileNotFoundError
        if isinstance(args.command, str):
            cmd = shlex.split(args.command)
        else:
            cmd = args.command

        completed = subprocess.run(
            cmd,
            cwd=args.working_directory or os.getcwd(),
            env={**os.environ, **args.env} if args.env else os.environ,
            capture_output=True,
            text=True,
            timeout=(args.timeout_ms / 1000) if args.timeout_ms else None,
        )
        return completed.stdout + completed.stderr

    except subprocess.TimeoutExpired:
        return "Command execution timed out"
    except Exception as e:
        return f"Error executing command: {str(e)}"

LocalShellTool = ShellTool
