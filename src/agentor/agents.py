"""
from agentor import Agentor

agent = Agentor(
    name="Agentor",
    instructions="You are an agent that can run agents.",
    model="gpt-4o",
    tools=[get_weather],
    mcp=[read_email, read_calendar]
)

result = agent.run("what is the weather in Tokyo?", stream=True)
for event in result.stream_events():
    print(event)


tasks = agent.plan("I need to book a flight to Tokyo")
for task in tasks:
    print(task)

for task in tasks:
    result = agent.act(task)
    print(result)
"""

import litellm
from typing import Callable, Literal, TypedDict
from typing import Any, Dict, Optional, List


from agentor.prompts import THINKING_PROMPT, render_prompt


def tool(func: Callable) -> Callable:
    if func.__doc__ is None:
        func.__doc__ = ""

    func_tool: Tool = litellm.utils.function_to_dict(func)  # type: ignore
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


class Agentor:
    def __init__(
        self, name: str, instructions: str, model: str, tools: list[Callable] = []
    ):
        self.name = name
        self.instructions = instructions
        self.model = model
        self.tools: List[Tool] = list(
            map(lambda tool: litellm.utils.function_to_dict(tool), tools)
        )
        self.tool_registry: Dict[str, Callable] = {
            tool_dict["name"]: tool for (tool, tool_dict) in zip(tools, self.tools)
        }

    def think(self, query: str) -> List[str] | str:
        prompt = render_prompt(THINKING_PROMPT, tools=self.tools)
