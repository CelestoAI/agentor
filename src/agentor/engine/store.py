"""Run persistence.

Durability falls out of the event stream: the events already describe a run
completely, so persisting them is the whole mechanism, and resuming is
replaying them into a message list. Forking falls out of it the same way:
copying the log to a new id copies the entire trace, and the two runs never
touch each other again. There is no second state model to keep in sync with
the loop.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol, runtime_checkable

from agentor.engine.events import Event, Usage

logger = logging.getLogger(__name__)


def new_run_id() -> str:
    return uuid.uuid4().hex


@runtime_checkable
class Store(Protocol):
    """Append-only event log per run.

    A store may additionally implement `fork(src_run_id, dst_run_id)` - copy
    one run's full log to a new id, raising ValueError if the destination
    already exists. `fork_run` uses it in place of its event-by-event
    fallback; both bundled stores provide one.
    """

    def append(self, run_id: str, event: Event) -> None: ...

    def load(self, run_id: str) -> List[Event]: ...

    def list_runs(self) -> List[str]: ...


class FileStore:
    """One append-only JSONL file per run."""

    def __init__(self, directory: str | Path = "runs"):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path(self, run_id: str) -> Path:
        # Ids become filenames. Reject anything that could land the file
        # outside the runs directory ("../x", "/tmp/x", "a\\b", "C:evil") or
        # hide it (".foo") - real ids are uuid hex, so this refuses nothing
        # legitimate, and it keeps a caller-supplied fork_id from becoming an
        # arbitrary-path write.
        if (
            not run_id
            or run_id.startswith(".")
            or any(sep in run_id for sep in ("/", "\\", ":"))
        ):
            raise ValueError(f"Invalid run id {run_id!r}.")
        return self.directory / f"{run_id}.jsonl"

    def append(self, run_id: str, event: Event) -> None:
        path = self.path(run_id)
        with path.open("a", encoding="utf-8") as f:
            # A hard kill mid-write can leave the file ending in a torn
            # fragment with no newline. Appending straight onto it would merge
            # this event into the fragment and make both unreadable - so the
            # recovery append itself would corrupt the log it is recovering.
            # Terminate the fragment first; load() already skips torn lines.
            if f.tell() > 0:
                with path.open("rb") as tail:
                    tail.seek(-1, os.SEEK_END)
                    if tail.read(1) != b"\n":
                        f.write("\n")
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
        # glob matches dotfiles, so filter with the same rule path() enforces -
        # otherwise a foreign file in the directory yields an id that load()
        # then refuses
        return sorted(
            p.stem
            for p in self.directory.glob("*.jsonl")
            if not p.stem.startswith(".")
            and not any(sep in p.stem for sep in ("/", "\\", ":"))
        )

    def fork(self, src_run_id: str, dst_run_id: str) -> None:
        """Copy one run's log to a new id in a single write.

        `append` fsyncs per event, which is right for a live run and needlessly
        slow when copying a long finished one. Re-serialises via `load` rather
        than copying the file so a torn final line is not carried into the
        fork, where the next append would land on the fragment and corrupt
        both. "x" mode refuses an existing file, so a concurrent fork onto the
        same id fails loudly instead of interleaving.
        """
        events = self.load(src_run_id)
        try:
            with self.path(dst_run_id).open("x", encoding="utf-8") as f:
                for event in events:
                    f.write(event.to_json() + "\n")
                f.flush()
                os.fsync(f.fileno())
        except FileExistsError:
            # e.g. an empty leftover file, which load() reports as no run
            raise ValueError(
                f"Run {dst_run_id!r} already exists; choose an unused id."
            ) from None


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

    def fork(self, src_run_id: str, dst_run_id: str) -> None:
        """Copy one run's log to a new id.

        setdefault claims the id and installs the copy in one dict operation,
        so a concurrent fork onto the same id fails loudly rather than
        silently overwriting. The JSON round-trip gives the fork its own Event
        objects; handing over the live ones would let a mutation through one
        log show up in the other.
        """
        copied = [
            Event.from_dict(json.loads(event.to_json()))
            for event in self.runs.get(src_run_id, [])
        ]
        if self.runs.setdefault(dst_run_id, copied) is not copied:
            raise ValueError(f"Run {dst_run_id!r} already exists; choose an unused id.")


def fork_run(store: Store, run_id: str, fork_id: Optional[str] = None) -> str:
    """Copy a run's event log to a new id, so the copy can evolve independently.

    The fork keeps the parent's entire trace - every generation with its
    request snapshot and reasoning, every tool call and result - and ends with
    a `fork` marker recording which run it came from. From then on the two
    logs are independent: appending to one never touches the other.

    Returns the fork's run id. Raises KeyError when the parent has no events
    and ValueError when `fork_id` is already in use. Collision detection is
    atomic only when the store provides a `fork` hook (both bundled stores
    do); the event-by-event fallback is check-then-copy.
    """
    events = store.load(run_id)
    if not events:
        raise KeyError(f"No persisted run with id {run_id!r}.")

    fork_id = fork_id or new_run_id()
    if store.load(fork_id):
        raise ValueError(f"Run {fork_id!r} already exists; choose an unused id.")

    copy = getattr(store, "fork", None)
    if callable(copy):
        copy(run_id, fork_id)
    else:
        for event in events:
            # round-trip through JSON so the fork owns its events outright: a
            # store handing back live objects (MemoryStore does) would
            # otherwise share them between the two logs
            store.append(fork_id, Event.from_dict(json.loads(event.to_json())))

    now = time.time()
    store.append(
        fork_id,
        Event(type="fork", forked_from=run_id, started_at=now, ended_at=now),
    )
    return fork_id


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
        if event.type == "run_start":
            # A later run_start opens a new segment (a resume or a fork
            # continuation) and snapshots the full request as it stood then -
            # including input added after the previous segment finished. If it
            # crashed before its first generation, that snapshot is the only
            # record of the new input, so recovery must restart from it, not
            # from an earlier segment's generation.
            start = event
            last_generation = None
            trailing = []
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
    """Whether the log's latest segment finished successfully.

    Scoped to the last segment rather than any(): a forked or resumed log can
    carry an earlier segment's completed run_end, and counting that would make
    resume() return the stale answer as "completed" while an interrupted
    continuation sits after it, unrecoverable.
    """
    for event in reversed(events):
        if event.type == "run_start":
            # a segment opened after the last terminal event: still in flight
            return False
        if event.type == "run_end":
            return event.status == "completed"
    return False


def final_event(events: List[Event]) -> Optional[Event]:
    for event in reversed(events):
        if event.type == "run_end":
            return event
    return None


def total_usage(events: List[Event]) -> Usage:
    """Sum every generation in the log.

    Deliberately not the terminal event's usage: a resumed run has one
    `run_end` per segment, and the last one counts only the continuation, so
    reading it would silently drop everything spent before the resume.
    """
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
    "fork_run",
    "is_complete",
    "new_run_id",
    "replay_messages",
    "total_usage",
]
