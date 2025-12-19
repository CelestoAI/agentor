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
