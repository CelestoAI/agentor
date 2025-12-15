from unittest.mock import patch

import litellm
from agents import FunctionTool

from agentor import Agentor, tool
from agentor.core.llm import LLM, ToolType
from agentor.core.tool import BaseTool


@tool
def add(a: int, b: int) -> int:
    """Add two numbers."""
    return a + b


def test_tool_decorator_creates_dual_mode_wrapper():
    assert isinstance(add, BaseTool)

    fn_tool = add.to_openai_function()[0]
    assert isinstance(fn_tool, FunctionTool)

    llm_fn = add.json_schema()[0]
    assert llm_fn["name"] == "add"
    assert llm_fn["description"]
    assert "properties" in llm_fn["parameters"]


def test_agentor_accepts_tool_convertor():
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        api_key="test",
        tools=[add],
    )
    assert agent.tools
    assert isinstance(agent.tools[0], FunctionTool)


@tool
def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello {name}"


@patch("agentor.core.llm.litellm")
def test_llm_uses_llm_function_format(mock_litellm):
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

    mock_litellm.responses.return_value = litellm.responses(
        model="", input="", mock_response="This is a test."
    )

    llm = LLM(model="gpt-5-mini", api_key="test")
    resp = llm.chat("", tools=[tool_definition])
    assert resp.output[-1].content[0].text == "This is a test."
