"""Agentor's native agent engine.

Self-contained by design: nothing here imports openai-agents, so removing that
dependency in a later phase is a deletion rather than a rewrite.
"""

from agentor.engine.events import Event, RunResult, Usage
from agentor.engine.loop import AgentLoop
from agentor.engine.models import (
    ChatCompletionsModel,
    LiteLLMModel,
    Model,
    ModelResponse,
    ToolCall,
    resolve_model,
)
from agentor.engine.tools import Tool, build_schema, parse_docstring, resolve_tools

__all__ = [
    "AgentLoop",
    "ChatCompletionsModel",
    "Event",
    "LiteLLMModel",
    "Model",
    "ModelResponse",
    "RunResult",
    "Tool",
    "ToolCall",
    "Usage",
    "build_schema",
    "parse_docstring",
    "resolve_model",
    "resolve_tools",
]
