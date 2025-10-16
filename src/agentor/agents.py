import json
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict

import litellm

from agentor.prompts import THINKING_PROMPT, render_prompt


def _function_to_tool(func: Callable):
    # Ensure docstring is a string to avoid dedent(None) -> TypeError
    if func.__doc__ is None:
        func.__doc__ = ""
    result = litellm.utils.function_to_dict(func)
    return {"type": "function", "function": result}


def tool(func: Callable) -> Callable:
    func_tool: Tool = _function_to_tool(func)  # type: ignore
    setattr(func, "_tool", func_tool)
    return func


class ToolFunctionParameters(TypedDict, total=False):
    type: str
    properties: Dict[str, Any]
    required: List[str]


class ToolFunction(TypedDict, total=False):
    name: str
    description: Optional[str]
    parameters: ToolFunctionParameters


class Tool(TypedDict):
    type: Literal["function"]
    function: ToolFunction


def get_dummy_weather(city: str) -> str:
    """Returns the dummy weather in the given city."""
    return f"The dummy weather in {city} is sunny"


class Agentor:
    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str] = None,
        tools: list[Callable] = [],
    ):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.tools: List[Tool] = list(map(lambda t: _function_to_tool(t), tools))
        self.tool_registry: Dict[str, Callable] = {
            tool_dict["function"]["name"]: tool
            for (tool, tool_dict) in zip(tools, self.tools)
        }

    def think(self, query: str) -> List[str] | str:
        prompt = render_prompt(
            THINKING_PROMPT,
            query=query,
            instructions=self.instructions,
            tools=self.tools,
        )
        messages = [{"role": "user", "content": prompt}]
        response = litellm.completion(
            model=self.model,
            messages=messages,
            tools=self.tools,
        )
        tool_calls = response.choices[0].message.tool_calls

        messages.append(
            {
                "role": "assistant",
                "content": response.choices[0].message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        if tool_calls:
            for tool_call in tool_calls:
                tool_name = tool_call.function.name
                tool_args = tool_call.function.arguments
                tool = self.tool_registry[tool_name]
                result = tool(**json.loads(tool_args))
                messages.append(
                    {
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": tool_name,
                        "content": result,
                    }
                )

            response = litellm.completion(
                model=self.model,
                messages=messages,
                tools=self.tools,
            )
        return response.choices[0].message.content
