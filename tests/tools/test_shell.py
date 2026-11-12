import asyncio

from pytest import fixture

from agentor.tools import ShellTool
from agentor.tools.shell import ShellCommandRequest


@fixture
def tool_request() -> ShellCommandRequest:
    return ShellCommandRequest(command="echo 'Hello, World!'")


def test_local_shell_tool(tool_request: ShellCommandRequest):
    tool = ShellTool()
    result = tool.run(tool_request)
    assert result == "Hello, World!\n"


def mock_sandbox_executor(request: ShellCommandRequest) -> str:
    return "109 files"


def test_local_shell_tool_with_sandbox_executor(tool_request: ShellCommandRequest):
    tool = ShellTool(executor=mock_sandbox_executor)
    result = tool.run(tool_request)
    assert result == "109 files"


def test_shell_tool_called_by_agent_loop_gets_a_request():
    received = []

    def executor(request: ShellCommandRequest) -> str:
        received.append(request)
        return "ok"

    (tool,) = ShellTool(executor=executor).to_openai_function()
    result = asyncio.run(
        tool.call({"request": {"command": "ls", "working_directory": "/tmp"}})
    )

    assert result == "ok"
    assert received == [ShellCommandRequest(command="ls", working_directory="/tmp")]
