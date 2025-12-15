# This example uses any LLM supported by LiteLLM, e.g. "gemini/gemini-3-pro-preview" or "anthropic/claude-4".

import os

from agentor import Agentor, function_tool


@function_tool
def get_weather(city: str):
    """Get the weather of city"""
    return f"Weather in {city} is sunny"


agent = Agentor(
    name="Weather Agent",
    model="gemini/gemini-3-pro-preview",
    tools=[get_weather],
    api_key=os.environ.get("GEMINI_API_KEY"),
)
result = agent.run("What is the weather in London?")
print(result)
