from typing import Any, AsyncIterator, List, Literal, Optional, Union
from xml.etree.ElementTree import Element, SubElement, tostring

from pydantic import BaseModel
from agentor.type_helper import serialize
from agents import (
    StreamEvent,
    RawResponsesStreamEvent,
    RunItemStreamEvent,
    AgentUpdatedStreamEvent,
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


async def format_stream_events(
    events: AsyncIterator[StreamEvent],
    output_format: Literal["json", "dict", "python"] = "python",
    allowed_events: Optional[
        List[Literal["agent_updated", "raw_response", "run_item"]]
    ] = None,
) -> AsyncIterator[Union[str, dict, StreamEvent]]:
    dump_json = output_format == "json"
    async for event in events:
        stream_event = format_event(event)

        if allowed_events is not None:
            if stream_event.type not in allowed_events:
                continue
        if dump_json:
            yield serialize(stream_event, dump_json=dump_json)
        elif output_format == "dict":
            yield serialize(stream_event)
        elif output_format == "python":
            yield stream_event
        else:
            raise ValueError(f"Invalid output format: {output_format}")


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
