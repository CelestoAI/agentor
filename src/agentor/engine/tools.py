"""Tool definition and JSON-schema generation for the native engine.

One `Tool` type, built from whatever the caller already has: a plain function,
a `BaseTool` capability, an openai-agents `FunctionTool`, or a registry name.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, get_type_hints

from pydantic import create_model

# Matches "name: description" or "name (type): description" inside an Args:
# block, which is the Google style used across agentor's own tools.
_ARG_LINE = re.compile(r"^\s*(\*{0,2}\w+)\s*(?:\([^)]*\))?\s*:\s*(.+)$")
_SECTION = re.compile(
    r"^\s*(Args|Arguments|Parameters|Returns|Raises|Yields|Examples?|Notes?)\s*:\s*$",
    re.IGNORECASE,
)


def parse_docstring(doc: Optional[str]) -> tuple[str, Dict[str, str]]:
    """Split a docstring into (summary, {param: description}).

    Supports the Google style used by agentor's tools. Param descriptions
    matter: without them the model gets a bare type and guesses more.
    """
    if not doc:
        return "", {}

    lines = inspect.cleandoc(doc).splitlines()
    summary: List[str] = []
    params: Dict[str, str] = {}
    section: Optional[str] = None
    current: Optional[str] = None

    for line in lines:
        header = _SECTION.match(line)
        if header:
            section = header.group(1).lower()
            current = None
            continue

        if section in ("args", "arguments", "parameters"):
            match = _ARG_LINE.match(line)
            if match:
                current = match.group(1).lstrip("*")
                params[current] = match.group(2).strip()
            elif current and line.strip():
                # continuation of the previous parameter's description
                params[current] += " " + line.strip()
        elif section is None:
            summary.append(line)

    return "\n".join(summary).strip(), params


def _strip_titles(schema: Any) -> Any:
    """Drop pydantic's auto-generated `title` keys.

    They carry no meaning for tool calling and are sent on every request.
    """
    if isinstance(schema, dict):
        return {
            k: _strip_titles(v)
            for k, v in schema.items()
            if k != "title" or not isinstance(v, str)
        }
    if isinstance(schema, list):
        return [_strip_titles(item) for item in schema]
    return schema


def _is_context_param(annotation: Any) -> bool:
    """True for a parameter that receives the run context, matched by name.

    `RunContextWrapper` is openai-agents' spelling and is still accepted, so
    tools written against the old engine keep working without an edit.
    """
    text = str(annotation)
    return "RunContext" in text or "RunContextWrapper" in text


def build_schema(
    fn: Callable, skip: Optional[set[str]] = None
) -> tuple[str, Dict[str, Any], Optional[str]]:
    """Derive (description, json_schema, context_param) from a callable."""
    skip = set(skip or ())
    summary, param_docs = parse_docstring(inspect.getdoc(fn))

    try:
        hints = get_type_hints(fn, include_extras=True)
    except Exception:
        # Unresolvable forward refs shouldn't make a tool unusable.
        hints = getattr(fn, "__annotations__", {}) or {}

    context_param: Optional[str] = None
    fields: Dict[str, Any] = {}

    for name, param in inspect.signature(fn).parameters.items():
        if name in ("self", "cls") or name in skip:
            continue
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            continue

        annotation = hints.get(name, str)
        if context_param is None and _is_context_param(annotation):
            context_param = name
            continue

        default = ... if param.default is inspect.Parameter.empty else param.default
        fields[name] = (annotation, default)

    model = create_model(f"{getattr(fn, '__name__', 'tool')}_args", **fields)
    schema = _strip_titles(model.model_json_schema())
    schema.setdefault("properties", {})
    schema.setdefault("required", [])

    for name, description in param_docs.items():
        prop = schema["properties"].get(name)
        if isinstance(prop, dict) and "description" not in prop:
            prop["description"] = description

    return summary, schema, context_param


@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    invoke: Callable[..., Any]
    #: parameter that receives the run context instead of model-supplied args
    context_param: Optional[str] = None

    def to_openai(self) -> Dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    async def call(self, args: Dict[str, Any], context: Any = None) -> str:
        kwargs = dict(args)
        if self.context_param:
            kwargs[self.context_param] = _ContextWrapper(context)
        if inspect.iscoroutinefunction(self.invoke):
            result = await self.invoke(**kwargs)
        else:
            # Most BaseTool capabilities are sync and do blocking IO. Calling
            # them inline would serialize the parallel tool calls the loop
            # gathers, and stall every other coroutine on the loop with them.
            result = await asyncio.to_thread(lambda: self.invoke(**kwargs))
            if inspect.isawaitable(result):
                result = await result
        return stringify(result)

    @classmethod
    def from_function(
        cls,
        fn: Callable,
        name: Optional[str] = None,
        description: Optional[str] = None,
    ) -> "Tool":
        summary, schema, context_param = build_schema(fn)
        return cls(
            name=name or getattr(fn, "__name__", "tool"),
            description=description or summary,
            parameters=schema,
            invoke=fn,
            context_param=context_param,
        )


def function_tool(
    func: Optional[Callable] = None,
    *,
    name_override: Optional[str] = None,
    description_override: Optional[str] = None,
) -> Any:
    """Turn a function into a `Tool`.

    Compatible with the decorator agentor exported previously, including
    `name_override`, so existing tool definitions need no change.

    Example::

        @function_tool
        def get_weather(city: str) -> str:
            "Return the weather for a city."
            return f"{city}: sunny"
    """

    def decorator(fn: Callable) -> Tool:
        return Tool.from_function(
            fn, name=name_override, description=description_override
        )

    if func is not None:
        return decorator(func)
    return decorator


class RunContext:
    """Wrapper handed to a tool parameter annotated as the run context.

    A tool declares `ctx: RunContext` and reads `ctx.context` to reach whatever
    the agent was constructed with. openai-agents' `RunContextWrapper`
    annotation is still recognised, so existing tools need no change.
    """

    __slots__ = ("context",)

    def __init__(self, context: Any = None):
        self.context = context


#: previous name, kept so old annotations and imports keep resolving
_ContextWrapper = RunContext


def stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if hasattr(value, "model_dump"):
        try:
            return json.dumps(value.model_dump(), default=str)
        except Exception:
            pass
    if isinstance(value, (dict, list, tuple, int, float, bool)):
        try:
            return json.dumps(value, default=str)
        except Exception:
            pass
    return str(value)


def resolve_tools(tools: Optional[List[Any]]) -> List[Tool]:
    """Normalize anything tool-shaped into a list of `Tool`."""
    from agentor.tools.base import BaseTool

    resolved: List[Tool] = []
    for item in tools or []:
        if isinstance(item, Tool):
            resolved.append(item)

        elif isinstance(item, str):
            from agentor.tools.registry import ToolRegistry

            entry = ToolRegistry.get(item)
            # The registry stores the undecorated function alongside the
            # openai-agents tool; the raw function is what we want.
            resolved.append(Tool.from_function(entry["function"], name=item))

        elif isinstance(item, BaseTool):
            for attr_name, method in item.list_capabilities():
                resolved.append(Tool.from_function(method, name=attr_name))

        elif callable(item):
            resolved.append(Tool.from_function(item))

        elif isinstance(getattr(item, "name", None), str):
            # Tool-shaped - it carries a name - but with nothing to invoke.
            # That covers provider-hosted tools, whose body lives on the
            # provider, and SDK-specific tool types whose execution is driven
            # by a runner agentor does not use. The message deliberately does
            # not assert which: both are unrunnable here, and guessing wrong
            # sends the reader looking in the wrong place.
            raise TypeError(
                f"{type(item).__name__} ({item.name!r}) exposes no callable to "
                "invoke, so agentor cannot run it. Provider-hosted tools (web "
                "search, file search) and SDK-specific tool types are not "
                "supported; define a function tool instead."
            )

        else:
            raise TypeError(
                f"Unsupported tool type {type(item).__name__!r}. Expected a "
                "callable, a Tool, a BaseTool, a FunctionTool, or a registry name."
            )

    return resolved
