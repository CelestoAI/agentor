from __future__ import annotations

from typing import Any, Callable, Optional, overload

from agentor.tools import BaseTool

ToolFunc = Callable[..., Any]


@overload
def tool(func: ToolFunc, /) -> BaseTool: ...


@overload
def tool(
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> Callable[[ToolFunc], BaseTool]: ...


def tool(
    func: Optional[ToolFunc] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    """
    Decorator to create a dual-mode tool usable by both Agentor and the simple LLM client.

    Example:
        >>> @tool
        ... def get_weather(city: str):
        ...     return "The weather in London is sunny"
    """

    tool_name = name or func.__name__
    tool_description = description or func.__doc__

    def decorator(fn: ToolFunc) -> BaseTool:
        return BaseTool.from_function(fn, name=tool_name, description=tool_description)

    if func is not None:
        # Used as @tool
        return decorator(func)

    # Used as @tool(...)
    return decorator
