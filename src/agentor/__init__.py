import warnings
from typing import TYPE_CHECKING

warnings.filterwarnings("ignore", category=DeprecationWarning)

__version__ = "0.1.0rc2"

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
    "LiteLLMModel",
    "AgentLoop",
    "Tool",
    "LLM",
]

# Import cost lives behind __getattr__ so `import agentor` stays cheap: pulling
# the engine costs ~1.2s (openai-agents), and litellm another ~1.0s on top.
# Users of agentor.tools, or of the CLI, should not pay for either.
# TYPE_CHECKING keeps type checkers and IDE completion working as before.
if TYPE_CHECKING:
    from agentor.core.agent import Agentor, CelestoMCPHub
    from agentor.core.llm import LLM
    from agentor.core.tool import tool
    from agentor.engine.models import LiteLLMModel as LitellmModel
    from agentor.engine.settings import ModelSettings
    from agentor.engine.tools import function_tool
    from agentor.tool_search import ToolSearch

    from .output_text_formatter import pydantic_to_xml
    from .utils import AppContext


_LAZY_ATTRS = {
    "Agentor": ("agentor.core.agent", "Agentor"),
    "CelestoMCPHub": ("agentor.core.agent", "CelestoMCPHub"),
    "ModelSettings": ("agentor.engine.settings", "ModelSettings"),
    "LLM": ("agentor.core.llm", "LLM"),
    "tool": ("agentor.core.tool", "tool"),
    "ToolSearch": ("agentor.tool_search", "ToolSearch"),
    "function_tool": ("agentor.engine.tools", "function_tool"),
    # kept under the old name; LiteLLMModel is the native adapter
    "LitellmModel": ("agentor.engine.models", "LiteLLMModel"),
    "LiteLLMModel": ("agentor.engine.models", "LiteLLMModel"),
    "AgentLoop": ("agentor.engine.loop", "AgentLoop"),
    "Tool": ("agentor.engine.tools", "Tool"),
    "pydantic_to_xml": ("agentor.output_text_formatter", "pydantic_to_xml"),
    "AppContext": ("agentor.utils", "AppContext"),
}


def __getattr__(name):
    if name in _LAZY_ATTRS:
        import importlib

        module_name, attr = _LAZY_ATTRS[name]
        value = getattr(importlib.import_module(module_name), attr)
        globals()[name] = value  # cache so later lookups skip __getattr__
        return value
    if name == "CelestoSDK":
        try:
            from celesto.sdk.client import CelestoSDK as _CelestoSDK
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "CelestoSDK is now provided by the separate 'celesto' package. "
                "Install it with `pip install celesto`."
            ) from exc
        globals()["CelestoSDK"] = _CelestoSDK
        return _CelestoSDK
    if name == "core":
        import importlib

        agents_module = importlib.import_module(".core", package=__name__)
        globals()["core"] = agents_module
        return agents_module
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(__all__ + ["core"])
