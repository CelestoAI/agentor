import os
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
)

from agentor.tools.registry import CelestoConfig, ToolRegistry
from agents import Agent, FunctionTool, Runner, function_tool
from agentor.prompts import THINKING_PROMPT, render_prompt

from agentor.output_text_formatter import format_stream_events

from pydantic import BaseModel

from .a2a import AgentServer


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


class APIInputRequest(BaseModel):
    input: Union[str, List[Dict[str, str]]]
    stream: bool = False


class Agentor(AgentServer):
    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str] = "gpt-5-nano",
        tools: List[Union[FunctionTool, str]] = [],
        debug: bool = False,
    ):
        super().__init__(debug=debug)
        tools = [
            ToolRegistry.get(tool)["tool"] if isinstance(tool, str) else tool
            for tool in tools
        ]
        self.name = name
        self.instructions = instructions
        self.model = model

        if os.environ.get("OPENAI_API_KEY") is None:
            raise ValueError("""OPENAI_API_KEY is required to use the Agentor.
            Please set the OPENAI_API_KEY environment variable.""")
        self.agent: Agent = Agent(
            name=name, instructions=instructions, model=model, tools=tools
        )

    def run(self, input: str) -> List[str] | str:
        return Runner.run_sync(self.agent, input, context=CelestoConfig())

    def think(self, query: str) -> List[str] | str:
        prompt = render_prompt(
            THINKING_PROMPT,
            query=query,
        )
        result = Runner.run_sync(self.agent, prompt, context=CelestoConfig())
        return result.final_output

    async def chat(
        self,
        input: str,
        stream: bool = False,
        output_format: Literal["json", "python"] = "python",
    ):
        if stream:
            return await self.stream_chat(input, output_format=output_format)
        else:
            return await Runner.run(self.agent, input=input, context=CelestoConfig())

    async def stream_chat(
        self,
        input: str,
        dump_json: bool = False,
    ):
        result = Runner.run_streamed(self.agent, input=input, context=CelestoConfig())
        async for agent_output in format_stream_events(
            result.stream_events(),
            allowed_events=["run_item_stream_event"],
        ):
            yield agent_output.serialize(dump_json=dump_json)
