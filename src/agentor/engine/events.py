"""Normalized events emitted by the agent loop.

This is deliberately the *only* description of what happened during a run.
Streaming, the final result, and the Celesto trace payload are all projections
of this stream, so there is no second format to keep in sync.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Literal, Optional

EventType = Literal[
    "run_start",
    "text_delta",
    "message",
    "tool_call",
    "tool_result",
    "run_end",
    "error",
]

RunStatus = Literal["completed", "max_turns", "failed"]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


@dataclass
class Event:
    type: EventType
    #: assistant text: the full message for `message`, one chunk for `text_delta`
    text: Optional[str] = None
    #: tool name for `tool_call` / `tool_result`
    name: Optional[str] = None
    #: parsed tool arguments
    args: Optional[Dict[str, Any]] = None
    #: stringified tool return value
    result: Optional[str] = None
    #: set on `tool_result` when the tool raised, and on `error`
    error: Optional[str] = None
    #: links a tool_result back to its tool_call
    call_id: Optional[str] = None
    #: 1-based, so events can be grouped into turns without replaying the loop
    turn: Optional[int] = None
    usage: Optional[Usage] = None
    status: Optional[RunStatus] = None
    agent: Optional[str] = None
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


@dataclass
class RunResult:
    """Terminal state of a run. Carries the events that produced it."""

    final_output: Optional[str] = None
    status: RunStatus = "completed"
    events: List[Event] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    #: full message list, suitable for feeding back in to continue the conversation
    messages: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None

    def __str__(self) -> str:
        return self.final_output or ""

    @property
    def tool_calls(self) -> List[Event]:
        return [e for e in self.events if e.type == "tool_call"]
