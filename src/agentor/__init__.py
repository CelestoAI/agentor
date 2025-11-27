import warnings

from agents import function_tool

from agentor.agents.core import Agentor, CelestoMCPHub, LitellmModel, ModelSettings
from agentor.sdk.client import CelestoSDK

from .output_text_formatter import pydantic_to_xml
from .proxy import create_proxy
from .utils import AppContext

warnings.filterwarnings("ignore", category=DeprecationWarning)

__version__ = "0.0.15.dev1"

__all__ = [
    "Agentor",
    "create_proxy",
    "pydantic_to_xml",
    "AppContext",
    "Memory",
    "CelestoSDK",
    "function_tool",
    "CelestoMCPHub",
    "ModelSettings",
    "LitellmModel",
]


# Lazy import agents and Memory to avoid triggering heavy dependency loading
def __getattr__(name):
    if name == "agents":
        import importlib

        agents_module = importlib.import_module(".agents", package=__name__)
        # Cache the module to avoid repeated imports
        globals()["agents"] = agents_module
        return agents_module
    if name == "Memory":
        from .memory.api import Memory

        globals()["Memory"] = Memory
        return Memory
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
