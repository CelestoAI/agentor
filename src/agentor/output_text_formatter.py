import json
from typing import Any, AsyncIterator, List, Literal, Optional, Union
from xml.etree.ElementTree import Element, SubElement, tostring

from agents import (
    AgentUpdatedStreamEvent,
    ItemHelpers,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    StreamEvent,
)
from attr import dataclass
from openai.types.responses import ResponseTextDeltaEvent
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
    type: Literal[
        "tool_called",
        "tool_output",
        "handoff_requested",
        "handoff_occured",
        "mcp_approval_requested",
        "mcp_approval_response",
        "mcp_list_tools",
    ]


@dataclass
class AgentOutput:
    type: Literal[
        "agent_updated_stream_event", "raw_response_event", "run_item_stream_event"
    ]
    message: Optional[str] = None
    chunk: Optional[str] = None
    tool_action: Optional[ToolAction] = None
    reasoning: Optional[str] = None
    raw_event: Optional[RawResponsesStreamEvent] = None

    def serialize(self, dump_json: bool = False) -> str:
        if dump_json:
            return json.dumps(serialize(self), indent=2) + "\n"
        return serialize(self)


def _extract_tool_name(raw_item: Any) -> Optional[str]:
    if raw_item is None:
        return None

    if isinstance(raw_item, BaseModel):
        data = raw_item.model_dump()
        for key in ("name", "tool_name", "call_id", "id", "type"):
            value = data.get(key)
            if value:
                return str(value)
        return raw_item.__class__.__name__

    for attr in ("name", "tool_name", "call_id", "id", "type"):
        value = getattr(raw_item, attr, None)
        if value:
            return str(value)

    return raw_item.__class__.__name__


def _stringify_output(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, BaseModel):
        return pydantic_to_xml(value)
    return str(value)


AllowedEventTypes = Literal[
    "agent_updated_stream_event", "raw_response_event", "run_item_stream_event"
]


async def format_stream_events(
    events: AsyncIterator[StreamEvent],
    allowed_events: Optional[List[AllowedEventTypes]] = None,
) -> AsyncIterator[AgentOutput]:
    """
    Formats a stream of events into a stream of AgentOutput objects.

    - raw_response_event: Events directly from the OpenAI Response API.
    - agent_updated_stream_event: Events from the Agent updated stream.
    - run_item_stream_event: Events from the Run Item stream.
    """
    async for event in events:
        stream_event = format_event(event)

        if allowed_events is not None:
            if stream_event.type not in allowed_events:
                continue

        if stream_event.type == "agent_updated_stream_event":
            yield AgentOutput(
                type="agent_updated_stream_event",
                message=stream_event.new_agent.name,
            )

        elif stream_event.type == "raw_response_event":
            data = stream_event.data
            if isinstance(data, ResponseTextDeltaEvent):
                chunk_text = data.delta or ""
                yield AgentOutput(
                    type="raw_response_event",
                    chunk=chunk_text,
                    raw_event=stream_event,
                )
            else:
                yield AgentOutput(
                    type="raw_response_event",
                    raw_event=stream_event,
                )

        elif stream_event.type == "run_item_stream_event":
            item = stream_event.item
            item_type = getattr(item, "type", None)

            if item_type == "message_output_item":
                yield AgentOutput(
                    type="run_item_stream_event",
                    message=ItemHelpers.text_message_output(item).strip(),
                )
            elif item_type == "tool_call_item":
                tool_name = _extract_tool_name(getattr(item, "raw_item", None))
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=tool_name or "tool_call_item", type="tool_called"
                    ),
                )
            elif item_type == "tool_call_output_item":
                tool_name = _extract_tool_name(getattr(item, "raw_item", None))
                output_text = _stringify_output(getattr(item, "output", None))
                yield AgentOutput(
                    type="run_item_stream_event",
                    message=output_text,
                    tool_action=ToolAction(
                        name=tool_name or "tool_call_output_item", type="tool_output"
                    ),
                )
            elif item_type == "reasoning_item":
                reasoning_text = getattr(getattr(item, "raw_item", None), "content", "")
                if reasoning_text is None:
                    reasoning_text = ""
                else:
                    reasoning_text = str(reasoning_text)
                yield AgentOutput(
                    type="run_item_stream_event",
                    reasoning=reasoning_text,
                )
            elif item_type == "handoff_call_item":
                target_name = _extract_tool_name(getattr(item, "raw_item", None))
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=target_name or "handoff_request",
                        type="handoff_requested",
                    ),
                )
            elif item_type == "handoff_output_item":
                source_agent = getattr(getattr(item, "source_agent", None), "name", "")
                target_agent = getattr(getattr(item, "target_agent", None), "name", "")
                action_name = " -> ".join(
                    part for part in (source_agent, target_agent) if part
                )
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=action_name or "handoff",
                        type="handoff_occured",
                    ),
                )
            elif item_type == "mcp_approval_request_item":
                request_name = _extract_tool_name(getattr(item, "raw_item", None))
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=request_name or "mcp_approval_request",
                        type="mcp_approval_requested",
                    ),
                )
            elif item_type == "mcp_approval_response_item":
                response_name = _extract_tool_name(getattr(item, "raw_item", None))
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=response_name or "mcp_approval_response",
                        type="mcp_approval_response",
                    ),
                )
            elif item_type == "mcp_list_tools_item":
                list_tools_name = _extract_tool_name(getattr(item, "raw_item", None))
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=list_tools_name or "mcp_list_tools",
                        type="mcp_list_tools",
                    ),
                )
            else:
                yield AgentOutput(
                    type="run_item_stream_event",
                    message=f"Unhandled run item type: {item_type or stream_event.name}",
                )

        else:
            raise ValueError(f"Invalid event type: {stream_event.type}")


def format_event(event: Union[StreamEvent, dict]) -> StreamEvent:
    if isinstance(event, dict):
        if event["type"] == "agent_updated":
            event = _format_agent_updated_stream_event(event)
        elif event["type"] == "raw_response":
            event = _format_raw_responses_stream_event(event)
        elif event["type"] == "run_item":
            event = _format_run_item_stream_event(event)
        else:
            raise ValueError(f"Invalid event type: {event['type']}")

    return event


def _format_agent_updated_stream_event(
    event: Union[AgentUpdatedStreamEvent, dict],
) -> AgentUpdatedStreamEvent:
    if isinstance(event, dict):
        event = AgentUpdatedStreamEvent(**event)
    return event


def _format_raw_responses_stream_event(
    event: Union[RawResponsesStreamEvent, dict],
) -> RawResponsesStreamEvent:
    if isinstance(event, dict):
        event = RawResponsesStreamEvent(**event)
    return event


def _format_run_item_stream_event(
    event: Union[RunItemStreamEvent, dict],
) -> RunItemStreamEvent:
    if isinstance(event, dict):
        event = RunItemStreamEvent(**event)
    return event
