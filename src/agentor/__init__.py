import warnings

from agents import function_tool

from agentor.agents.core import Agentor, CelestoMCPHub, LitellmModel, ModelSettings
from agentor.sdk.client import CelestoSDK

from .output_text_formatter import pydantic_to_xml
from .utils import AppContext

warnings.filterwarnings("ignore", category=DeprecationWarning)

__version__ = "0.0.16.dev1"

__all__ = [
    "Agentor",
    "pydantic_to_xml",
    "AppContext",
    "CelestoSDK",
    "function_tool",
    "CelestoMCPHub",
    "ModelSettings",
    "LitellmModel",
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
