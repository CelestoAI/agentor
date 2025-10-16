from agentor.prompts import THINKING_PROMPT, render_prompt
from agentor.agents import tool


@tool
def get_weather(city: str) -> str:
    return f"The weather in {city} is sunny"


def test_tool_decorator():
    assert get_weather("London") == "The weather in London is sunny"
    print(get_weather._tool)


def test_prompt_rendering():
    prompt = render_prompt(
        THINKING_PROMPT, query="What is the weather in London?", tools=[]
    )
    print(prompt)


test_prompt_rendering()
