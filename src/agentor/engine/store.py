"""Run persistence.

Durability falls out of the event stream: the events already describe a run
completely, so persisting them is the whole mechanism, and resuming is
replaying them into a message list. There is no second state model to keep in
sync with the loop.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from agentor.engine.events import Event, Usage

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    return uuid.uuid4().hex


@runtime_checkable
class Store(Protocol):
    def append(self, run_id: str, event: Event) -> None: ...

    def load(self, run_id: str) -> List[Event]: ...

    def list_runs(self) -> List[str]: ...


class FileStore:
    """One append-only JSONL file per run."""

    def __init__(self, directory: str | Path = "runs"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        return self.directory / f"{run_id}.jsonl"

    def append(self, run_id: str, event: Event) -> None:
        with self.path(run_id).open("a", encoding="utf-8") as f:
            f.write(event.to_json() + "\n")
            # a crash is exactly the case this exists for, so do not leave the
            # last events sitting in a buffer
            f.flush()
            os.fsync(f.fileno())

    def load(self, run_id: str) -> List[Event]:
        path = self.path(run_id)
        if not path.exists():
            return []

        events: List[Event] = []
        with path.open("r", encoding="utf-8") as f:
            for line_number, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(Event.from_dict(json.loads(line)))
                except (json.JSONDecodeError, TypeError) as e:
                    # A torn final line is expected after a hard kill; earlier
                    # events are still usable, so keep what parsed.
                    logger.warning(
                        "Skipping unreadable event at %s:%d (%s)", path, line_number, e
                    )
        return events

    def list_runs(self) -> List[str]:
        return sorted(p.stem for p in self.directory.glob("*.jsonl"))


class MemoryStore:
    """In-process store, for tests and short-lived processes."""

    def __init__(self) -> None:
        self.runs: Dict[str, List[Event]] = {}

    def append(self, run_id: str, event: Event) -> None:
        self.runs.setdefault(run_id, []).append(event)

    def load(self, run_id: str) -> List[Event]:
        return list(self.runs.get(run_id, []))

    def list_runs(self) -> List[str]:
        return sorted(self.runs)


def replay_messages(events: List[Event]) -> List[Dict[str, Any]]:
    """Rebuild the model's message list from a persisted run.

    Each `generation` records the request exactly as it was sent, so the most
    recent one plus its own reply and any tool results that followed is the
    full conversation. Nothing needs to be inferred.
    """
    start: Optional[Event] = None
    last_generation: Optional[Event] = None
    trailing: List[Event] = []

    for event in events:
        if event.type == "run_start" and start is None:
            start = event
        elif event.type == "generation":
            last_generation = event
            trailing = []
        elif event.type == "tool_result" and last_generation is not None:
            trailing.append(event)

    if last_generation is None:
        # Crashed before the first response; the input recorded at run_start is
        # all that is needed to start over.
        return [dict(m) for m in (start.messages or [])] if start else []

    messages: List[Dict[str, Any]] = [dict(m) for m in (last_generation.messages or [])]

    requested = {
        call.get("id") for call in (last_generation.calls or []) if call.get("id")
    }
    answered = {event.call_id for event in trailing if event.call_id}

    if requested - answered:
        # The run stopped between requesting tools and recording every result.
        # Replaying the assistant turn would send tool_calls with no matching
        # tool messages, which providers reject outright, and the unfinished
        # tools would never run. Rewind to the request that produced it and let
        # the model decide again.
        return messages

    assistant: Dict[str, Any] = {"role": "assistant", "content": last_generation.text}
    if last_generation.calls:
        assistant["tool_calls"] = last_generation.calls
    messages.append(assistant)

    for event in trailing:
        messages.append(
            {
                "role": "tool",
                "tool_call_id": event.call_id,
                "content": event.result or "",
            }
        )
    return messages


def is_complete(events: List[Event]) -> bool:
    return any(e.type == "run_end" and e.status == "completed" for e in events)


def final_event(events: List[Event]) -> Optional[Event]:
    for event in reversed(events):
        if event.type == "run_end":
            return event
    return None


def total_usage(events: List[Event]) -> Usage:
    end = final_event(events)
    if end is not None and end.usage is not None:
        return end.usage
    total = Usage()
    for event in events:
        if event.type == "generation" and event.usage:
            total = total + event.usage
    return total


__all__ = [
    "FileStore",
    "MemoryStore",
    "Store",
    "final_event",
    "is_complete",
    "new_run_id",
    "replay_messages",
    "total_usage",
]
