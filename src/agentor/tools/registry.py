import os
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, List, Union

from dotenv import load_dotenv

from agentor.engine.tools import RunContext, function_tool
from agentor.engine.tools import Tool as FunctionTool

from .weather import GetWeatherTool

load_dotenv()


@dataclass
class CelestoConfig:
    weather_api_key: str | None = os.environ.get("WEATHER_API_KEY")


_GLOBAL_TOOLS: dict[str, Union[FunctionTool, Callable]] = {}


def register_global_tool(func):
    llm_fn = function_tool(func)
    _GLOBAL_TOOLS[func.__name__] = {
        "tool": llm_fn,
        "function": func,
    }
    return llm_fn


@register_global_tool
def get_weather(wrapper: RunContext, city: str) -> str:
    """Returns the weather in the given city.

    Args:
        city: The city to look up.
    """
    try:
        weather_tool = GetWeatherTool(api_key=wrapper.context.weather_api_key)
        return weather_tool.get_current_weather(city)
    except Exception as e:
        return f"Failed to get weather data: {e}"


@register_global_tool
def current_datetime(wrapper: RunContext) -> str:
    """Returns the current date and time."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class ToolRegistry:
    """Registry for tools."""

    @staticmethod
    def get(name: str) -> Union[FunctionTool, Callable]:
        try:
            return _GLOBAL_TOOLS[name]
        except KeyError:
            raise ValueError(f"Tool {name} not found")

    @staticmethod
    def list() -> List[str]:
        return tuple(_GLOBAL_TOOLS.keys())

    @staticmethod
    def __len__() -> int:
        return len(_GLOBAL_TOOLS)
