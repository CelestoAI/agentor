from unittest.mock import MagicMock, patch

from agents import FunctionTool

from agentor import Agentor, tool
from agentor.core.llm import LLM
from agentor.core.tool import ToolConvertor


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def test_tool_decorator_creates_dual_mode_wrapper():
    assert isinstance(add, ToolConvertor)

    fn_tool = add.to_function_tool()
    assert isinstance(fn_tool, FunctionTool)

    llm_fn = add.to_llm_function()
    assert llm_fn["name"] == "add"
    assert llm_fn["description"]
    assert "properties" in llm_fn["parameters"]


def test_agentor_accepts_tool_convertor():
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        llm_api_key="test",
        tools=[add],
    )
    assert agent.tools
    assert isinstance(agent.tools[0], FunctionTool)


@tool
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello {name}"


@patch("agentor.core.llm.responses")
def test_llm_uses_llm_function_format(mock_responses):
    output_item = MagicMock()
    output_item.type = "function_call"
    output_item.name = "greet"
    output_item.arguments = {"name": "Alex"}

    mock_response = MagicMock()
    mock_response.output = [output_item]
    mock_responses.return_value = mock_response

    llm = LLM(model="gpt-5-mini", api_key="test")
    result = llm.chat("Say hi", tools=[greet], call_tools=True)

    assert result.outputs[0].tool_output == "Hello Alex"
    assert mock_responses.called
    sent_tools = mock_responses.call_args.kwargs["tools"]
    assert sent_tools[0]["name"] == "greet"
