from agentor.tools.base import BaseTool


def weather_tool(city: str):
    "This function returns the weather of the city."
    return f"Weather in {city} is warm and sunny."


def test_from_function():
    tool = BaseTool.from_function(weather_tool)
    assert tool.run("London") == "Weather in London is warm and sunny."
    assert tool.name == "weather_tool"
    assert tool.description == "This function returns the weather of the city."
