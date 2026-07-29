"""Tool definition and JSON-schema generation for the native engine.

One `Tool` type, built from whatever the caller already has: a plain function,
a `BaseTool` capability, an openai-agents `FunctionTool`, or a registry name.
"""

from __future__ import annotations

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
    """True for openai-agents' RunContextWrapper, matched by name.

    Matching the name rather than importing keeps this module free of an
    openai-agents dependency, so the engine survives that package's removal.
    """
    return "RunContextWrapper" in str(annotation)


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

        result = self.invoke(**kwargs)
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


class _ContextWrapper:
    """Minimal stand-in for openai-agents' RunContextWrapper.

    Legacy tools declare `wrapper: RunContextWrapper[CelestoConfig]` and read
    `wrapper.context`; supporting that attribute is the whole compatibility
    surface. Phase 2 removes the need for this.
    """

    __slots__ = ("context",)

    def __init__(self, context: Any = None):
        self.context = context


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


def _from_function_tool(ft: Any) -> Tool:
    """Adapt an openai-agents FunctionTool.

    Its `on_invoke_tool(ctx, args_json)` takes a JSON string, so arguments are
    re-serialized on the way in.
    """
    invoker = ft.on_invoke_tool

    async def invoke(**kwargs: Any) -> Any:
        return await invoker(_ContextWrapper(None), json.dumps(kwargs))

    return Tool(
        name=ft.name,
        description=ft.description or "",
        parameters=_strip_titles(dict(ft.params_json_schema or {})),
        invoke=invoke,
    )


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

        elif callable(item) and hasattr(item, "on_invoke_tool"):
            resolved.append(_from_function_tool(item))

        elif callable(item):
            resolved.append(Tool.from_function(item))

        else:
            raise TypeError(
                f"Unsupported tool type {type(item).__name__!r}. Expected a "
                "callable, a Tool, a BaseTool, a FunctionTool, or a registry name."
            )

    return resolved
