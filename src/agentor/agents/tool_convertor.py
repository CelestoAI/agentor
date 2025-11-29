from __future__ import annotations

from functools import update_wrapper
from typing import Any, Callable, Dict, Optional

from agents import FunctionTool, function_tool


class ToolConvertor:
    """
    Wrapper returned by the @tool decorator.

    - For Agentor usage, convert to an `agents.function_tool` via `to_function_tool`.
    - For the lightweight LLM client, expose an OpenAI/LiteLLM compatible function
      definition via `to_llm_function`.
    """

    def __init__(
        self,
        func: Callable[..., Any],
        *,
        name_override: Optional[str] = None,
        description_override: Optional[str] = None,
    ) -> None:
        self._func = func
        self._function_tool = function_tool(
            func,
            name_override=name_override,
            description_override=description_override,
        )
        self._llm_function: Dict[str, Any] = {
            "name": self._function_tool.name,
            "description": self._function_tool.description,
            # LiteLLM deprecated `functions` format expects this shape
            "parameters": self._function_tool.params_json_schema,
        }
        # Mirror the wrapped function's metadata for better introspection.
        update_wrapper(self, func)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self._func(*args, **kwargs)

    @property
    def name(self) -> str:
        return self._function_tool.name

    @property
    def description(self) -> str:
        return self._function_tool.description

    @property
    def params_json_schema(self) -> Dict[str, Any]:
        return self._function_tool.params_json_schema

    def to_function_tool(self) -> FunctionTool:
        """Return the wrapped `FunctionTool` for Agentor."""
        return self._function_tool

    def to_llm_function(self) -> Dict[str, Any]:
        """Return the LiteLLM-style function definition."""
        return self._llm_function


def tool(
    func: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> ToolConvertor | Callable[[Callable[..., Any]], ToolConvertor]:
    """
    Decorator to create a dual-mode tool usable by both Agentor and the simple LLM client.

    Example:
        >>> @tool
        ... def get_weather(city: str):
        ...     return "The weather in London is sunny"
    """

    def decorator(fn: Callable[..., Any]) -> ToolConvertor:
        return ToolConvertor(
            fn,
            name_override=name,
            description_override=description,
        )

    if callable(func):
        return decorator(func)

    return decorator
