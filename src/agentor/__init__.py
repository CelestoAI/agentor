from .cli import app
from .memory.api import Memory
from .output_text_formatter import pydantic_to_xml
from .proxy import create_proxy
from .utils import AppContext
from agentor.sdk.client import CelestoSDK

__version__ = "0.0.2"

__all__ = [
    "app",
    "create_proxy",
    "pydantic_to_xml",
    "AppContext",
    "Memory",
    "CelestoSDK",
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
