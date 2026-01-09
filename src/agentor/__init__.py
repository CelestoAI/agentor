import warnings

from agents import function_tool

from agentor.core.agent import Agentor, CelestoMCPHub, LitellmModel, ModelSettings
from agentor.core.llm import LLM
from agentor.core.tool import tool
from agentor.tool_search import ToolSearch
from celesto_sdk.sdk.client import CelestoSDK

from .output_text_formatter import pydantic_to_xml
from .utils import AppContext

warnings.filterwarnings("ignore", category=DeprecationWarning)

__version__ = "0.0.19"

__all__ = [
    "Agentor",
    "pydantic_to_xml",
    "AppContext",
    "CelestoSDK",
    "function_tool",
    "ToolSearch",
    "tool",
    "CelestoMCPHub",
    "ModelSettings",
    "LitellmModel",
    "LLM",
    "ToolSearch",
]


# Lazy import core to avoid triggering Google agent initialization
def __getattr__(name):
    if name == "core":
        import importlib

        agents_module = importlib.import_module(".core", package=__name__)
        # Cache the module to avoid repeated imports
        globals()["core"] = agents_module
        return agents_module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
