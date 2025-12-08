from __future__ import annotations

from typing import Any, Callable, Optional

from agentor.tools import BaseTool


def tool(
    func: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
) -> BaseTool:
    """
    Decorator to create a dual-mode tool usable by both Agentor and the simple LLM client.

    Example:
        >>> @tool
        ... def get_weather(city: str):
        ...     return "The weather in London is sunny"
    """

    def decorator(fn: Callable[..., Any]) -> BaseTool:
        return BaseTool(
            fn,
            name_override=name,
            description_override=description,
        )

    if callable(func):
        return decorator(func)

    return decorator
