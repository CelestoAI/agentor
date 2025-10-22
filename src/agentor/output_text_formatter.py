from typing import Any, AsyncIterator, List, Literal, Optional, Union
from xml.etree.ElementTree import Element, SubElement, tostring

from attr import dataclass
from pydantic import BaseModel
from agents import (
    StreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    AgentUpdatedStreamEvent,
    ItemHelpers,
)


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


async def format_stream_events(
    events: AsyncIterator[StreamEvent],
    allowed_events: Optional[
        List[
            Literal[
                "agent_updated_stream_event",
                "raw_response_event",
                "run_item_stream_event",
            ]
        ]
    ] = None,
) -> AsyncIterator[Union[str, dict, StreamEvent]]:
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
            yield AgentOutput(
                type="raw_response_event",
                raw_event=stream_event.data,
            )

        elif stream_event.type == "run_item_stream_event":
            if stream_event.name == "message_output_created":
                yield AgentOutput(
                    type="run_item_stream_event",
                    message=ItemHelpers.text_message_output(stream_event.item),
                )
            elif stream_event.name == "tool_called":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.raw_item.name, type="tool_called"
                    ),
                )
            elif stream_event.name == "tool_output":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.raw_item, type="tool_output"
                    ),
                )
            elif stream_event.name == "handoff_requested":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.name, type="handoff_requested"
                    ),
                )
            elif stream_event.name == "handoff_occured":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.name, type="handoff_occured"
                    ),
                )
            elif stream_event.name == "mcp_approval_requested":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.name, type="mcp_approval_requested"
                    ),
                )
            elif stream_event.name == "mcp_list_tools":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.name, type="mcp_list_tools"
                    ),
                )
            elif stream_event.name == "reasoning_item_created":
                yield AgentOutput(
                    type="run_item_stream_event",
                    reasoning=stream_event.item.raw_item.content,
                )
            elif stream_event.name == "mcp_approval_response":
                yield AgentOutput(
                    type="run_item_stream_event",
                    tool_action=ToolAction(
                        name=stream_event.item.name, type="mcp_approval_response"
                    ),
                )
            else:
                print(f"Unhandled event name: {stream_event.name}")

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
