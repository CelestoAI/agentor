import os
import shlex
import subprocess

from pydantic import BaseModel

from agentor.tools import BaseTool, capability


class LocalShellCommandRequest(BaseModel):
    command: str
    working_directory: str | None = None
    env: dict | None = None
    timeout_ms: int | None = None


class LocalShellTool(BaseTool):
    name = "local_shell"
    description = "Execute shell commands"

    @capability
    def run(self, request: LocalShellCommandRequest):
        return _shell_executor(request)


def _shell_executor(request: LocalShellCommandRequest) -> str:
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
