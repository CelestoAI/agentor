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
    name: str
    #: The engine reports a call and its result; the handoff and mcp-approval
    #: variants this once carried came from the openai-agents item stream and
    #: were never emitted again after the engine took over.
    type: Literal["tool_called", "tool_output"]


@dataclass
class AgentOutput:
    #: `_native_stream` projects every engine event onto this one variant. The
    #: other two openai-agents event names are gone with the SDK.
    type: Literal["run_item_stream_event"]
    message: Optional[str] = None
    chunk: Optional[str] = None
    tool_action: Optional[ToolAction] = None
    reasoning: Optional[str] = None
    raw_event: Optional[Any] = None

    def serialize(self, dump_json: bool = False) -> str:
        if dump_json:
            return json.dumps(serialize(self), indent=2) + "\n"
        return serialize(self)
