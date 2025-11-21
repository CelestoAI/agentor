import warnings

from agents import function_tool

from agentor.agents.core import Agentor, CelestoMCPHub
from agentor.sdk.client import CelestoSDK

from .memory.api import Memory
from .output_text_formatter import pydantic_to_xml
from .proxy import create_proxy
from .utils import AppContext

warnings.filterwarnings("ignore", category=DeprecationWarning)

__version__ = "0.0.14"

__all__ = [
    "Agentor",
    "create_proxy",
    "pydantic_to_xml",
    "AppContext",
    "Memory",
    "CelestoSDK",
    "function_tool",
    "CelestoMCPHub",
]


# Lazy import agents to avoid triggering Google agent initialization
def __getattr__(name):
    if name == "agents":
        import importlib

        agents_module = importlib.import_module(".agents", package=__name__)
        # Cache the module to avoid repeated imports
        globals()["agents"] = agents_module
        return agents_module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
