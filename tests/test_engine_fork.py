"""Tests for forking runs and for the reasoning capture that makes a fork's
trace complete (agentor.engine.store.fork_run, AgentLoop.afork).

A fork copies a run's whole event log - request snapshots, reasoning, tool
calls and results - to a new id, and the two runs act independently from that
point on.
"""

import json
import sys
from types import SimpleNamespace

import pytest

from agentor.engine import AgentLoop
from agentor.engine.events import Event, Usage
from agentor.engine.models import ChatCompletionsModel, ModelResponse
from agentor.engine.store import (
    FileStore,
    MemoryStore,
    fork_run,
    is_complete,
    replay_messages,
    total_usage,
)
from agentor.engine.tracing import TraceCollector
from tests.test_engine import FakeModel, calls, text, weather

# ------------------------------------------------------------ fork_run


@pytest.mark.asyncio
async def test_fork_copies_the_full_log_and_marks_its_parent() -> None:
    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "A"}')), text("done")),
        tools=[weather],
        store=store,
    )
    parent = await loop.arun("go")

    fork_id = fork_run(store, parent.run_id)
    forked = store.load(fork_id)

    assert fork_id != parent.run_id
    # everything the parent recorded, then the marker
    assert [e.to_dict() for e in forked[:-1]] == [
        e.to_dict() for e in store.load(parent.run_id)
    ]
    assert forked[-1].type == "fork"
    assert forked[-1].forked_from == parent.run_id


@pytest.mark.asyncio
async def test_forked_events_are_independent_copies() -> None:
    """MemoryStore hands back live objects; the fork must still own its own."""
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")

    fork_id = fork_run(store, parent.run_id)
    store.load(fork_id)[0].agent = "mutated"

    assert store.load(parent.run_id)[0].agent != "mutated"


def test_fork_of_an_unknown_run_raises() -> None:
    with pytest.raises(KeyError, match="No persisted run"):
        fork_run(MemoryStore(), "nope")


@pytest.mark.asyncio
async def test_fork_refuses_an_id_already_in_use() -> None:
    """FileStore appends in "a" mode, so a collision would silently merge two
    runs into one log rather than fail."""
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")

    with pytest.raises(ValueError, match="already exists"):
        fork_run(store, parent.run_id, fork_id=parent.run_id)


@pytest.mark.asyncio
async def test_fork_marker_does_not_disturb_replay_or_completion() -> None:
    """The marker is provenance only; every reader of the log must see the
    forked run exactly as it saw the parent."""
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")

    forked = store.load(fork_run(store, parent.run_id))
    assert is_complete(forked)
    assert replay_messages(forked) == replay_messages(store.load(parent.run_id))
    assert total_usage(forked) == total_usage(store.load(parent.run_id))


@pytest.mark.asyncio
async def test_file_store_fork_round_trips_and_drops_a_torn_line(tmp_path) -> None:
    store = FileStore(tmp_path / "runs")
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")
    with store.path(parent.run_id).open("a") as f:
        f.write('{"type": "message", "text": "trunc')

    fork_id = fork_run(store, parent.run_id)

    # a fresh store over the same directory sees a clean, complete copy; had
    # the torn fragment been carried over, the marker appended after it would
    # have merged with it and both lines would be lost
    forked = FileStore(tmp_path / "runs").load(fork_id)
    assert [e.type for e in forked[:-1]] == [e.type for e in parent.events]
    assert forked[-1].type == "fork"


# ------------------------------------------------------------ AgentLoop.afork


@pytest.mark.asyncio
async def test_fork_continues_without_touching_the_parent() -> None:
    store = MemoryStore()
    loop = AgentLoop(model=FakeModel(text("first"), text("second")), store=store)
    parent = await loop.arun("go")
    parent_log = [e.to_dict() for e in store.load(parent.run_id)]

    result = await loop.afork(parent.run_id, "and then?")

    assert result.run_id != parent.run_id
    assert result.final_output == "second"
    # the whole history: the parent's events, the marker, the continuation
    assert [e.type for e in result.events[: len(parent.events)]] == [
        e.type for e in parent.events
    ]
    assert "fork" in [e.type for e in result.events]
    # ...and the whole cost, one generation on each side of the fork
    assert result.usage == Usage(2, 4, 6)
    # the parent run is exactly as it was
    assert [e.to_dict() for e in store.load(parent.run_id)] == parent_log


@pytest.mark.asyncio
async def test_fork_with_input_re_executes_a_completed_run() -> None:
    """resume() deliberately short-circuits a finished run; forking one with
    new input is the way to branch the conversation past its end."""
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("answer")), store=store).arun("go")

    model = FakeModel(text("branched"))
    result = await AgentLoop(model=model, store=store).afork(parent.run_id, "more")

    assert result.final_output == "branched"
    replayed = model.calls[0]["messages"]
    assert [m["role"] for m in replayed] == ["user", "assistant", "user"]
    assert replayed[1]["content"] == "answer"
    assert replayed[-1] == {"role": "user", "content": "more"}


@pytest.mark.asyncio
async def test_fork_without_input_of_a_completed_run_copies_only() -> None:
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("answer")), store=store).arun("go")

    model = FakeModel(text("should not be used"))
    result = await AgentLoop(model=model, store=store).afork(parent.run_id)

    assert model.calls == [], "forking a finished run must not call the model"
    assert result.run_id != parent.run_id
    assert result.final_output == "answer"
    assert result.status == "completed"
    assert [m["role"] for m in result.messages] == ["user", "assistant"]


@pytest.mark.asyncio
async def test_fork_without_input_completes_an_unfinished_run() -> None:
    store = MemoryStore()
    crashed = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "Oslo"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    parent = await crashed.arun("weather in Oslo?")
    assert parent.status == "max_turns"

    finisher = AgentLoop(model=FakeModel(text("sunny")), tools=[weather], store=store)
    result = await finisher.afork(parent.run_id)

    assert result.status == "completed"
    assert result.final_output == "sunny"
    # the parent stays interrupted; only the fork was finished
    assert not is_complete(store.load(parent.run_id))


@pytest.mark.asyncio
async def test_fork_requires_a_store() -> None:
    with pytest.raises(ValueError, match="requires a store"):
        await AgentLoop(model=FakeModel(text("x"))).afork("r1")


@pytest.mark.asyncio
async def test_fork_accepts_a_message_list_input() -> None:
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("a")), store=store).arun("go")

    model = FakeModel(text("b"))
    await AgentLoop(model=model, store=store).afork(
        parent.run_id, [{"role": "user", "content": "more"}]
    )
    assert model.calls[0]["messages"][-1] == {"role": "user", "content": "more"}


@pytest.mark.asyncio
async def test_fork_with_input_of_an_unreplayable_run_raises() -> None:
    """A log whose replay is empty cannot take new input; fail loudly."""
    store = MemoryStore()
    store.append("r1", Event(type="error", error="boom"))

    with pytest.raises(ValueError, match="no recoverable messages"):
        await AgentLoop(model=FakeModel(text("x")), store=store).afork("r1", "hi")


@pytest.mark.asyncio
async def test_fork_of_a_structured_output_run_returns_the_parsed_model() -> None:
    from pydantic import BaseModel

    class Answer(BaseModel):
        value: int

    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(text('{"value": 4}')), store=store, output_type=Answer
    )
    parent = await loop.arun("2+2?")

    result = await loop.afork(parent.run_id)
    assert result.final_output == Answer(value=4)


@pytest.mark.asyncio
async def test_fork_with_input_of_a_pending_tool_call_run_replays_validly() -> None:
    """Forking mid-tool-turn must not send dangling tool_calls to the model."""
    store = MemoryStore()
    # a run persisted between requesting a tool and recording its result
    store.append(
        "r1", Event(type="run_start", messages=[{"role": "user", "content": "q"}])
    )
    store.append(
        "r1",
        Event(
            type="generation",
            messages=[{"role": "user", "content": "q"}],
            calls=[
                {
                    "id": "c0",
                    "type": "function",
                    "function": {"name": "weather", "arguments": "{}"},
                }
            ],
        ),
    )

    model = FakeModel(text("done"))
    await AgentLoop(model=model, tools=[weather], store=store).afork(
        "r1", "actually, Bergen"
    )

    replayed = model.calls[0]["messages"]
    # the unanswered tool turn is rewound, not sent dangling
    assert all("tool_calls" not in m for m in replayed)
    assert replayed[-1] == {"role": "user", "content": "actually, Bergen"}


@pytest.mark.asyncio
async def test_fork_forwards_max_turns_to_an_unfinished_continuation() -> None:
    store = MemoryStore()
    crashed = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "A"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    parent = await crashed.arun("go")

    # the continuation also keeps asking for tools, so only the forwarded
    # budget of 1 (not the loop default of 10) explains a max_turns result
    finisher = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "B"}'))),
        tools=[weather],
        store=store,
    )
    result = await finisher.afork(parent.run_id, max_turns=1)
    assert result.status == "max_turns"


@pytest.mark.asyncio
async def test_file_store_fork_refuses_an_existing_empty_destination(
    tmp_path,
) -> None:
    """An empty leftover file defeats the load() pre-check; the write itself
    must still fail with the documented ValueError, not FileExistsError."""
    store = FileStore(tmp_path / "runs")
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")
    store.path("taken").touch()

    with pytest.raises(ValueError, match="already exists"):
        fork_run(store, parent.run_id, fork_id="taken")


@pytest.mark.asyncio
async def test_resume_of_a_completed_run_populates_messages() -> None:
    """RunResult.messages is documented as feed-back-in ready; the completed
    short-circuit must honour that the same way a continued run does."""
    store = MemoryStore()
    loop = AgentLoop(model=FakeModel(text("answer")), store=store)
    parent = await loop.arun("go")

    resumed = await loop.aresume(parent.run_id)
    assert [m["role"] for m in resumed.messages] == ["user", "assistant"]


def test_from_dict_tolerates_unknown_usage_keys() -> None:
    """A newer writer's extra usage field must not delete the whole event."""
    restored = Event.from_dict(
        {
            "type": "generation",
            "usage": {
                "input_tokens": 1,
                "output_tokens": 2,
                "total_tokens": 3,
                "reasoning_tokens": 9,
            },
        }
    )
    assert restored.usage == Usage(1, 2, 3)


@pytest.mark.asyncio
async def test_resume_of_an_interrupted_fork_continuation_re_executes() -> None:
    """The parent's completed run_end lives in the fork's log; it must not
    make resume() report a crashed continuation as already finished."""
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("old")), store=store).arun("go")

    stuck = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    forked = await stuck.afork(parent.run_id, "new question")
    assert forked.status == "max_turns"

    resumed = await AgentLoop(
        model=FakeModel(text("fresh")), tools=[weather], store=store
    ).aresume(forked.run_id)
    assert resumed.status == "completed"
    assert resumed.final_output == "fresh"


def test_is_complete_judges_only_the_latest_segment() -> None:
    completed = [Event(type="run_start"), Event(type="run_end", status="completed")]
    assert is_complete(completed)
    # a continuation opened after the completed segment reopens the run
    assert not is_complete(completed + [Event(type="run_start")])
    assert not is_complete(
        completed + [Event(type="run_start"), Event(type="run_end", status="max_turns")]
    )
    # a trailing fork marker reopens nothing
    assert is_complete(completed + [Event(type="fork", forked_from="p")])


def test_replay_recovers_fork_input_from_a_pre_generation_crash() -> None:
    """Crash after the continuation's run_start but before its first
    generation: that run_start snapshot is the only record of the new input."""
    events = [
        Event(type="run_start", messages=[{"role": "user", "content": "q"}]),
        Event(
            type="generation",
            messages=[{"role": "user", "content": "q"}],
            text="old answer",
        ),
        Event(type="run_end", status="completed", text="old answer"),
        Event(type="fork", forked_from="parent"),
        Event(
            type="run_start",
            messages=[
                {"role": "user", "content": "q"},
                {"role": "assistant", "content": "old answer"},
                {"role": "user", "content": "new question"},
            ],
        ),
    ]
    messages = replay_messages(events)
    assert messages[-1] == {"role": "user", "content": "new question"}


@pytest.mark.parametrize(
    "bad", ["../escape", "/tmp/x", "a/b", "..\\win", "C:evil", ".hidden", ""]
)
def test_file_store_rejects_unsafe_run_ids(tmp_path, bad) -> None:
    """Ids become filenames; anything that could leave the runs directory (or
    hide inside it) must fail loudly instead of writing elsewhere."""
    store = FileStore(tmp_path / "runs")
    with pytest.raises(ValueError, match="Invalid run id"):
        store.path(bad)


@pytest.mark.asyncio
async def test_fork_refuses_a_traversal_fork_id(tmp_path) -> None:
    store = FileStore(tmp_path / "runs")
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")

    with pytest.raises(ValueError, match="Invalid run id"):
        fork_run(store, parent.run_id, fork_id="../escaped")
    assert not (tmp_path / "escaped.jsonl").exists()


@pytest.mark.asyncio
async def test_append_heals_a_torn_tail_before_writing(tmp_path) -> None:
    """Appending onto a torn fragment must not merge with it — the recovery
    append after a crash is exactly when the log matters most."""
    store = FileStore(tmp_path / "runs")
    store.append("r1", Event(type="run_start"))
    with store.path("r1").open("a") as f:
        f.write('{"type": "message", "text": "trunc')

    store.append("r1", Event(type="message", text="recovered"))

    events = store.load("r1")
    assert [e.type for e in events] == ["run_start", "message"]
    assert events[-1].text == "recovered"


@pytest.mark.asyncio
async def test_fork_run_falls_back_to_event_by_event_copy() -> None:
    """A custom store without a fork hook still gets a correct, owned copy."""

    class PlainStore:
        def __init__(self) -> None:
            self.runs: dict = {}

        def append(self, run_id, event) -> None:
            self.runs.setdefault(run_id, []).append(event)

        def load(self, run_id):
            return list(self.runs.get(run_id, []))

        def list_runs(self):
            return sorted(self.runs)

    store = PlainStore()
    parent = await AgentLoop(model=FakeModel(text("hi")), store=store).arun("go")

    fork_id = fork_run(store, parent.run_id)
    forked = store.load(fork_id)
    assert [e.to_dict() for e in forked[:-1]] == [
        e.to_dict() for e in store.load(parent.run_id)
    ]
    assert forked[-1].forked_from == parent.run_id
    # the fallback round-trips through JSON, so the copies are owned outright
    forked[0].agent = "mutated"
    assert store.load(parent.run_id)[0].agent != "mutated"


@pytest.mark.asyncio
async def test_fork_rejects_an_empty_list_input() -> None:
    with pytest.raises(ValueError, match="empty list"):
        await AgentLoop(model=FakeModel(text("x")), store=MemoryStore()).afork("r1", [])


@pytest.mark.asyncio
async def test_failed_fork_continuation_names_the_persisted_fork() -> None:
    """The copy is persisted before the continuation runs; the error must say
    which run id to resume, or the fork is stranded anonymously."""

    class ExplodingModel:
        model = "boom"

        async def complete(self, messages, tools=None, response_format=None):
            raise RuntimeError("provider down")

    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("ok")), store=store).arun("go")

    with pytest.raises(RuntimeError, match="provider down") as excinfo:
        await AgentLoop(model=ExplodingModel(), store=store).afork(
            parent.run_id, "more"
        )
    assert any("Forked run persisted" in n for n in excinfo.value.__notes__)


@pytest.mark.asyncio
async def test_fork_forwards_tracing_to_the_continuation() -> None:
    """tracing=False is a privacy promise; both afork branches must honour it."""
    from tests.test_engine_tracing import RecordingTracer

    tracer = RecordingTracer()
    store = MemoryStore()
    parent = await AgentLoop(model=FakeModel(text("a")), store=store).arun("go")

    loop = AgentLoop(model=FakeModel(text("b"), text("c")), store=store, tracer=tracer)
    await loop.afork(parent.run_id, "more", tracing=False)
    assert tracer.exported == [], "tracing=False must suppress export on a fork"

    await loop.afork(parent.run_id, "again")
    assert len(tracer.exported) == 1


@pytest.mark.asyncio
async def test_fork_without_input_forwards_tracing_through_resume() -> None:
    from tests.test_engine_tracing import RecordingTracer

    tracer = RecordingTracer()
    store = MemoryStore()
    crashed = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "A"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    parent = await crashed.arun("go")

    finisher = AgentLoop(
        model=FakeModel(text("done")), tools=[weather], store=store, tracer=tracer
    )
    result = await finisher.afork(parent.run_id, tracing=False)
    assert result.status == "completed"
    assert tracer.exported == []


# ------------------------------------------------------------ reasoning


@pytest.mark.asyncio
async def test_generation_event_carries_reasoning_and_survives_a_fork() -> None:
    """The point of forking is keeping the whole trace, so the reasoning has
    to be in the persisted events, not just the in-flight response."""
    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(
            ModelResponse(content="4", reasoning="2+2 is 4", usage=Usage(1, 2, 3))
        ),
        store=store,
    )
    parent = await loop.arun("2+2?")

    forked = store.load(fork_run(store, parent.run_id))
    generation = next(e for e in forked if e.type == "generation")
    assert generation.reasoning == "2+2 is 4"
    # and it round-trips through the log's JSON encoding
    assert Event.from_dict(json.loads(generation.to_json())).reasoning == "2+2 is 4"


@pytest.mark.asyncio
async def test_chat_completions_reads_reasoning_content() -> None:
    payload = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content="4", tool_calls=None, reasoning_content="2+2 is 4"
                )
            )
        ],
        usage=None,
    )

    async def create(**kwargs):
        return payload

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    response = await ChatCompletionsModel("m", client=client).complete(
        [{"role": "user", "content": "2+2?"}]
    )
    assert response.content == "4"
    assert response.reasoning == "2+2 is 4"


@pytest.mark.asyncio
async def test_streaming_accumulates_reasoning_deltas() -> None:
    """Covers the alternate `reasoning` field name some providers use."""

    def delta(**kwargs):
        chunk = SimpleNamespace(content=None, tool_calls=None)
        chunk.__dict__.update(kwargs)
        return SimpleNamespace(usage=None, choices=[SimpleNamespace(delta=chunk)])

    chunks = [
        delta(reasoning="think "),
        delta(reasoning="hard"),
        delta(content="answer"),
        SimpleNamespace(
            usage=SimpleNamespace(prompt_tokens=1, completion_tokens=2, total_tokens=3),
            choices=[],
        ),
    ]

    async def create(**kwargs):
        async def gen():
            for chunk in chunks:
                yield chunk

        return gen()

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    final = None
    async for chunk in ChatCompletionsModel("m", client=client).stream(
        [{"role": "user", "content": "q"}]
    ):
        if chunk.final is not None:
            final = chunk.final

    assert final.content == "answer"
    assert final.reasoning == "think hard"
    assert final.usage == Usage(1, 2, 3)


@pytest.mark.asyncio
async def test_litellm_complete_reads_reasoning_content(monkeypatch) -> None:
    message = SimpleNamespace(content="4", tool_calls=None, reasoning_content="2+2")
    raw = SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=None)

    async def acompletion(**kwargs):
        return raw

    monkeypatch.setitem(
        sys.modules, "litellm", SimpleNamespace(acompletion=acompletion)
    )
    from agentor.engine.models import LiteLLMModel

    response = await LiteLLMModel("prov/model").complete(
        [{"role": "user", "content": "2+2?"}]
    )
    assert response.content == "4"
    assert response.reasoning == "2+2"


def test_trace_span_carries_reasoning_only_when_present() -> None:
    collector = TraceCollector("wf")
    collector.handle(Event(type="run_start", started_at=1.0))
    collector.handle(
        Event(type="generation", text="plain", started_at=1.0, ended_at=2.0)
    )
    collector.handle(
        Event(
            type="generation",
            text="4",
            reasoning="2+2 is 4",
            started_at=2.0,
            ended_at=3.0,
        )
    )

    spans = [
        item["span_data"]
        for item in collector.items
        if item.get("span_data", {}).get("type") == "generation"
    ]
    assert "reasoning" not in spans[0]
    assert spans[1]["reasoning"] == "2+2 is 4"


# ------------------------------------------------------------ Agentor


def test_agentor_fork(tmp_path) -> None:
    from agentor import Agentor

    store = FileStore(tmp_path / "runs")
    agent = Agentor(
        name="T",
        model=FakeModel(text("hello"), text("branched")),
        engine="native",
        api_key="test",
        store=store,
    )
    parent = agent.run("go")

    result = agent.fork(parent.run_id, "keep going")
    assert result.run_id != parent.run_id
    assert result.final_output == "branched"
    # both runs live side by side in the store
    assert set(store.list_runs()) == {parent.run_id, result.run_id}
    assert agent.resume(parent.run_id).final_output == "hello"


@pytest.mark.asyncio
async def test_agentor_afork_honours_an_explicit_fork_id(tmp_path) -> None:
    from agentor import Agentor

    store = FileStore(tmp_path / "runs")
    agent = Agentor(
        name="T",
        model=FakeModel(text("hello"), text("branched")),
        engine="native",
        api_key="test",
        store=store,
    )
    parent = await agent.arun("go")

    result = await agent.afork(parent.run_id, "more", fork_id="custom")
    assert result.run_id == "custom"
    assert result.final_output == "branched"
