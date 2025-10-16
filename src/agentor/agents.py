from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
)
from agents import Runner

from agents import Agent, function_tool

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


@function_tool(name_override="get_weather")
def get_dummy_weather(city: str) -> str:
    """Returns the dummy weather in the given city."""
    return f"The dummy weather in {city} is sunny"


class Agentor:
    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str] = "gpt-5-nano",
        tools: list[Callable | Tool] = [],
    ):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.agent: Agent = Agent(
            name=name, instructions=instructions, model=model, tools=tools
        )

    def run(
        self, input: str, context: Optional[Dict[str, Any]] = None
    ) -> List[str] | str:
        return Runner.run_sync(self.agent, input, context=context)

    def think(self, query: str) -> List[str] | str:
        prompt = render_prompt(
            THINKING_PROMPT,
            query=query,
        )
        return self.run(prompt)

    async def chat(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AsyncGenerator:
        return await Runner.run_streamed(self.agent, input=input, context=context)
