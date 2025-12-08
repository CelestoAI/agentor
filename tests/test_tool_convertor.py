from unittest.mock import patch

from agents import FunctionTool

from agentor import Agentor, tool
from agentor.core.llm import LLM, ToolType
from agentor.core.tool import AgentTool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def test_tool_decorator_creates_dual_mode_wrapper():
    assert isinstance(add, AgentTool)

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


@patch("agentor.core.llm.litellm.responses")
def test_llm_uses_llm_function_format(mock_responses):
    tool_definition: ToolType = {
        "type": "function",
        "function": {
            "name": "greet",
            "description": "Return a greeting.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name to greet",
                    }
                },
                "required": ["name"],
            },
        },
    }

    llm = LLM(model="gpt-5-mini", api_key="test")
    llm.chat("", tools=[tool_definition])
