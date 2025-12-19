from pytest import fixture

from agentor.tools import LocalShellTool
from agentor.tools.shell import LocalShellCommandRequest


@fixture
def tool_request() -> LocalShellCommandRequest:
    return LocalShellCommandRequest(command="echo 'Hello, World!'")


def test_local_shell_tool(tool_request: LocalShellCommandRequest):
    tool = LocalShellTool()
    result = tool.run(tool_request)
    assert result == "Hello, World!\n"
