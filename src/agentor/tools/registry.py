import os
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Callable, List, Union

from agents import FunctionTool, RunContextWrapper, function_tool
from dotenv import load_dotenv

from celesto_sdk.sdk.client import CelestoSDK

load_dotenv()


@dataclass
class CelestoConfig:
    api_token: str = os.environ.get("CELESTO_API_TOKEN")
    base_url: str = "https://api.celesto.ai/v1"


_GLOBAL_TOOLS: dict[str, Union[FunctionTool, Callable]] = {}


@wraps(function_tool)
def register_global_tool(func):
    llm_fn = function_tool(func)
    _GLOBAL_TOOLS[func.__name__] = {
        "tool": llm_fn,
        "function": func,
    }
    return llm_fn


@register_global_tool
def get_weather(wrapper: RunContextWrapper[CelestoConfig], city: str) -> str:
    """Returns the weather in the given city."""
    try:
        client = CelestoSDK(wrapper.context.api_token)
        return client.toolhub.run_weather_tool(city)
    except Exception as e:
        print(f"Error: {e}")
        return "Failed to get weather data."


@register_global_tool
def list_emails(wrapper: RunContextWrapper[CelestoConfig], limit: int = 10) -> str:
    """Lists the emails from the given email address."""
    try:
        client = CelestoSDK(wrapper.context.api_token)
        return client.toolhub.run_list_google_emails(limit)
    except Exception as e:
        print(f"Error: {e}")
        return "Failed to list emails."


@register_global_tool
def send_email(
    wrapper: RunContextWrapper[CelestoConfig], to: str, subject: str, body: str
) -> str:
    """Sends an email to the given email address."""
    try:
        client = CelestoSDK(wrapper.context.api_token)
        return client.toolhub.run_send_google_email(to, subject, body)
    except Exception as e:
        print(f"Error: {e}")
        return "Failed to send email."


@register_global_tool
def current_datetime(wrapper: RunContextWrapper[CelestoConfig]) -> str:
    """Returns the current date and time."""
    try:
        client = CelestoSDK(wrapper.context.api_token)
        return client.toolhub.run_current_date_time()
    except Exception as e:
        print(f"Error: {e}")
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
