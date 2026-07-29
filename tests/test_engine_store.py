"""Tests for run persistence and resume (agentor.engine.store)."""

import json

import pytest

from agentor.engine import AgentLoop
from agentor.engine.events import Event, Usage
from agentor.engine.store import (
    FileStore,
    MemoryStore,
    is_complete,
    replay_messages,
    total_usage,
)
from tests.test_engine import FakeModel, calls, text, weather

# ------------------------------------------------------------ serialization


def test_event_roundtrips_through_json():
    event = Event(
        type="generation",
        text="hi",
        usage=Usage(1, 2, 3),
        messages=[{"role": "user", "content": "a"}],
        started_at=1.0,
        ended_at=2.0,
    )
    restored = Event.from_dict(json.loads(event.to_json()))

    assert restored.type == "generation"
    assert restored.usage == Usage(1, 2, 3)
    assert restored.messages == [{"role": "user", "content": "a"}]
    assert restored.ended_at == 2.0


def test_from_dict_ignores_unknown_fields():
    """A newer writer must not break an older reader of the same log."""
    restored = Event.from_dict({"type": "message", "text": "x", "brand_new_field": 1})
    assert restored.text == "x"


# ------------------------------------------------------------ FileStore


def test_file_store_append_and_load(tmp_path):
    store = FileStore(tmp_path / "runs")
    store.append("r1", Event(type="run_start", agent="A"))
    store.append("r1", Event(type="message", text="hello"))

    events = store.load("r1")
    assert [e.type for e in events] == ["run_start", "message"]
    assert events[1].text == "hello"
    assert store.list_runs() == ["r1"]


def test_file_store_load_missing_run_is_empty(tmp_path):
    assert FileStore(tmp_path).load("nope") == []


def test_file_store_tolerates_a_torn_final_line(tmp_path):
    """A hard kill mid-write must not make earlier events unreadable."""
    store = FileStore(tmp_path)
    store.append("r1", Event(type="run_start"))
    store.append("r1", Event(type="message", text="kept"))
    with store.path("r1").open("a") as f:
        f.write('{"type": "message", "text": "trunc')

    events = store.load("r1")
    assert [e.type for e in events] == ["run_start", "message"]
    assert events[1].text == "kept"


# ------------------------------------------------------------ replay


def test_replay_rebuilds_messages_including_tool_results():
    events = [
        Event(type="run_start"),
        Event(
            type="generation",
            messages=[{"role": "user", "content": "q"}],
            text=None,
            calls=[
                {
                    "id": "c0",
                    "type": "function",
                    "function": {"name": "weather", "arguments": "{}"},
                }
            ],
        ),
        Event(type="tool_result", call_id="c0", name="weather", result="sunny"),
    ]

    messages = replay_messages(events)
    assert [m["role"] for m in messages] == ["user", "assistant", "tool"]
    assert messages[1]["tool_calls"][0]["id"] == "c0"
    assert messages[2] == {"role": "tool", "tool_call_id": "c0", "content": "sunny"}


def test_replay_of_an_empty_log_is_empty():
    assert replay_messages([]) == []
    assert replay_messages([Event(type="run_start")]) == []


def test_total_usage_sums_generations_when_no_run_end():
    events = [
        Event(type="generation", usage=Usage(1, 2, 3)),
        Event(type="generation", usage=Usage(10, 20, 30)),
    ]
    assert total_usage(events) == Usage(11, 22, 33)


# ------------------------------------------------------------ persistence


@pytest.mark.asyncio
async def test_run_persists_every_event_and_returns_a_run_id():
    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "A"}')), text("done")),
        tools=[weather],
        store=store,
    )
    result = await loop.arun("go")

    assert result.run_id is not None
    persisted = store.load(result.run_id)
    assert [e.type for e in persisted] == [e.type for e in result.events]
    assert is_complete(persisted)


@pytest.mark.asyncio
async def test_no_store_means_no_run_id():
    result = await AgentLoop(model=FakeModel(text("x"))).arun("go")
    assert result.run_id is None


@pytest.mark.asyncio
async def test_store_failure_does_not_break_the_run():
    class Broken:
        def append(self, run_id, event):
            raise OSError("disk full")

        def load(self, run_id):
            return []

        def list_runs(self):
            return []

    loop = AgentLoop(model=FakeModel(text("still fine")), store=Broken())
    result = await loop.arun("go")
    assert result.final_output == "still fine"


# ------------------------------------------------------------ resume


@pytest.mark.asyncio
async def test_resume_continues_an_unfinished_run():
    """Simulates a crash: the first attempt stops mid-run, the second finishes."""
    store = MemoryStore()

    crashed = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "Oslo"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    first = await crashed.arun("weather in Oslo?")
    assert first.status == "max_turns"
    assert first.final_output is None

    resumed_loop = AgentLoop(
        model=FakeModel(text("It is sunny in Oslo.")),
        tools=[weather],
        store=store,
    )
    second = await resumed_loop.aresume(first.run_id)

    assert second.status == "completed"
    assert second.final_output == "It is sunny in Oslo."
    # the continuation is stitched onto the original history
    assert len(second.events) > len(first.events)


@pytest.mark.asyncio
async def test_resume_replays_the_tool_result_into_the_new_request():
    store = MemoryStore()
    crashed = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "Oslo"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    first = await crashed.arun("weather in Oslo?")

    model = FakeModel(text("done"))
    await AgentLoop(model=model, tools=[weather], store=store).aresume(first.run_id)

    roles = [m["role"] for m in model.calls[0]["messages"]]
    assert roles == ["user", "assistant", "tool"]
    assert model.calls[0]["messages"][-1]["content"] == "Oslo: sunny"


@pytest.mark.asyncio
async def test_resume_of_a_completed_run_does_not_re_execute():
    store = MemoryStore()
    loop = AgentLoop(model=FakeModel(text("original")), store=store)
    first = await loop.arun("go")

    model = FakeModel(text("should not be used"))
    resumed = await AgentLoop(model=model, store=store).aresume(first.run_id)

    assert resumed.final_output == "original"
    assert resumed.status == "completed"
    assert model.calls == [], "a finished run must not call the model again"


@pytest.mark.asyncio
async def test_resume_requires_a_store():
    with pytest.raises(ValueError, match="requires a store"):
        await AgentLoop(model=FakeModel(text("x"))).aresume("r1")


@pytest.mark.asyncio
async def test_resume_unknown_run_id_raises():
    with pytest.raises(KeyError, match="No persisted run"):
        await AgentLoop(model=FakeModel(text("x")), store=MemoryStore()).aresume("nope")


@pytest.mark.asyncio
async def test_resume_survives_a_real_file_round_trip(tmp_path):
    """The whole point: a fresh process picks the run up from disk."""
    store = FileStore(tmp_path / "runs")
    crashed = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "Rome"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    first = await crashed.arun("go")

    reopened = AgentLoop(
        model=FakeModel(text("recovered")),
        tools=[weather],
        store=FileStore(tmp_path / "runs"),
    )
    second = await reopened.aresume(first.run_id)
    assert second.final_output == "recovered"


# ------------------------------------------------------------ Agentor


def test_agentor_native_resume(tmp_path):
    from agentor import Agentor

    store = FileStore(tmp_path / "runs")
    agent = Agentor(
        name="T",
        model=FakeModel(text("hello")),
        engine="native",
        api_key="test",
        store=store,
    )
    result = agent.run("go")
    assert result.run_id is not None
    assert agent.resume(result.run_id).final_output == "hello"


def test_agentor_agents_engine_rejects_resume():
    from agentor import Agentor

    agent = Agentor(name="T", model="gpt-4o-mini", api_key="test")
    with pytest.raises(NotImplementedError, match="engine='native'"):
        agent.resume("r1")


def test_durable_agent_import_gives_a_migration_message():
    import agentor.durable as durable

    with pytest.raises(AttributeError, match="engine='native'"):
        durable.DurableAgent
