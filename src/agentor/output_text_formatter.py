import json
from typing import Any, Literal, Optional
from xml.etree.ElementTree import Element, SubElement, tostring

from attr import dataclass
from pydantic import BaseModel

from agentor.type_helper import serialize


def pydantic_to_xml(obj: BaseModel) -> str:
    def value_to_xml(parent: Element, key: str, value: Any):
        if isinstance(value, BaseModel):
            child = SubElement(parent, key)
            model_to_xml(child, value)
        elif isinstance(value, dict):
            child = SubElement(parent, key)
            for k, v in value.items():
                value_to_xml(child, k, v)
        elif isinstance(value, list):
            for item in value:
                value_to_xml(parent, key, item)
        else:
            child = SubElement(parent, key)
            child.text = str(value)

    def model_to_xml(parent: Element, model: BaseModel):
        model_dict = model.model_dump()
        for key, value in model_dict.items():
            value_to_xml(parent, key, value)

    root = Element(obj.__class__.__name__)
    model_to_xml(root, obj)
    return tostring(root, "utf-8").decode()


@dataclass
class ToolAction:
    """A tool invocation or its result, as reported on the stream.

    The engine reports exactly these two: the call, then what it returned. The
    handoff and mcp-approval variants this once carried came from the
    openai-agents item stream and stopped being emitted when the engine took
    over.

    Attributes:
        name: The tool's name.
        type: Whether this marks the call or its result.
    """

    name: str
    type: Literal["tool_called", "tool_output"]


@dataclass
class AgentOutput:
    """One event of a streamed run, as `stream_chat` and `/chat` emit it.

    `Agentor._native_stream` projects every engine event onto the single
    `run_item_stream_event` variant; the two other openai-agents event names
    went with the SDK.

    Attributes:
        type: The event variant. Only one remains.
        message: Assistant text, or a tool result, or a failure explanation.
        chunk: Unused by the engine; retained so the serialized shape is stable.
        tool_action: Set when this event concerns a tool.
        reasoning: Unused by the engine; retained for shape stability.
        raw_event: Unused by the engine; retained for shape stability.
    """

    type: Literal["run_item_stream_event"]
    message: Optional[str] = None
    chunk: Optional[str] = None
    tool_action: Optional[ToolAction] = None
    reasoning: Optional[str] = None
    raw_event: Optional[Any] = None

    def serialize(self, dump_json: bool = False) -> str:
        """Render the event, as a JSON object or as a plain mapping.

        Args:
            dump_json: Return indented JSON with a trailing newline rather than
                the serializable mapping.
        """
        if dump_json:
            return json.dumps(serialize(self), indent=2) + "\n"
        return serialize(self)
