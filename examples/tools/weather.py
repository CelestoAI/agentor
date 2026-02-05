"""End-to-end Agentor example: GetWeatherTool.

Environment:
    export WEATHER_API_KEY=your_weatherapi_key
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import GetWeatherTool


def main() -> None:
    weather_api_key = os.environ.get("WEATHER_API_KEY")
    if not weather_api_key:
        raise ValueError("WEATHER_API_KEY is required")

    agent = Agentor(
        name="Weather Agent",
        model="gpt-5-mini",
        tools=[GetWeatherTool(api_key=weather_api_key)],
        instructions="Always use the weather tool to answer weather questions.",
    )

    result = agent.run("What is the current weather in London?")
    print(result.final_output)


if __name__ == "__main__":
    main()
