import json
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
)
from google.adk.agents import Agent

from google.adk.models.lite_llm import LiteLlm

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
        model: Optional[str] = "gpt-5-nano",
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
        self.agent: Agent = Agent(
            name=name,
            instructions=instructions,
            model=LiteLlm(model=model),
            tools=tools,
        )

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

        if not tool_calls:
            return response.choices[0].message.content

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

        return litellm.completion(
            model=self.model,
            messages=messages,
            tools=self.tools,
        )

    def chat(
        self,
        messages: Union[List[Dict[str, Any]], str],
        stream: bool = False,
        max_tokens: Optional[int] = None,
    ) -> AsyncGenerator | str:
        if isinstance(messages, str):
            messages = [
                {"role": "system", "content": self.instructions},
                {"role": "user", "content": messages},
            ]
        if stream:
            return litellm.completion(
                model=self.model,
                messages=messages,
                tools=self.tools,
                stream=True,
                max_tokens=max_tokens,
            )
        else:
            return (
                litellm.completion(
                    model=self.model,
                    messages=messages,
                    tools=self.tools,
                    max_tokens=max_tokens,
                )
                .choices[0]
                .message.content
            )
