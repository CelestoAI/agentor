from typing import (
    Any,
    Callable,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
)

from agents import Agent, Runner, function_tool

from agentor.prompts import THINKING_PROMPT, render_prompt


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
        return self.run(prompt).final_output

    async def chat(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        return await Runner.run(self.agent, input=input, context=context)

    async def stream_chat(
        self,
        input: str,
        context: Optional[Dict[str, Any]] = None,
    ):
        result = Runner.run_streamed(self.agent, input=input, context=context)
        async for event in result.stream_events():
            yield event
