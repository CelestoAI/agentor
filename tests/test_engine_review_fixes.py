"""Regression tests for the findings raised in the codex review of the v0.1.0 stack.

Each test names the defect it pins down, so a future change that reintroduces
one fails with an explanation rather than a bare assertion.
"""

import asyncio
from typing import Optional

import pytest
from pydantic import BaseModel

from agentor.engine import AgentLoop
from agentor.engine.events import Event
from agentor.engine.loop import _strictify
from agentor.engine.mcp import MCPServer
from agentor.engine.store import MemoryStore, replay_messages
from tests.test_engine import FakeModel, calls, text, weather
from tests.test_engine_mcp import FakeSession, remote_tool


class Boom:
    """A model that always fails."""

    model = "boom"

    def __init__(self, message="provider down"):
        self.message = message

    async def complete(self, messages, tools=None, response_format=None):
        raise RuntimeError(self.message)

    async def stream(self, messages, tools=None, response_format=None):
        raise RuntimeError(self.message)
        yield  # pragma: no cover


# ------------------------------------------------- P1: durability of the input


@pytest.mark.asyncio
async def test_input_is_persisted_before_the_first_model_call():
    """A crash before the first response must still leave a resumable run."""
    store = MemoryStore()
    loop = AgentLoop(model=Boom(), store=store, instructions="sys")

    with pytest.raises(RuntimeError):
        await loop.arun("my important question")

    (run_id,) = store.list_runs()
    messages = replay_messages(store.load(run_id))
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[-1]["content"] == "my important question"


@pytest.mark.asyncio
async def test_resume_after_a_pre_response_crash():
    store = MemoryStore()
    with pytest.raises(RuntimeError):
        await AgentLoop(model=Boom(), store=store).arun("question")

    (run_id,) = store.list_runs()
    recovered = await AgentLoop(model=FakeModel(text("answer")), store=store).aresume(
        run_id
    )
    assert recovered.final_output == "answer"


# ------------------------------------------- P1: pending tool calls on resume


def test_replay_rewinds_past_unanswered_tool_calls():
    """Replaying tool_calls with no matching results is rejected by providers."""
    events = [
        Event(type="run_start", messages=[{"role": "user", "content": "q"}]),
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
        Event(type="tool_call", name="weather", call_id="c0"),
    ]

    messages = replay_messages(events)
    assert [m["role"] for m in messages] == ["user"], (
        "an assistant turn with unanswered tool_calls must not be replayed"
    )


def test_replay_rewinds_on_partially_answered_tool_calls():
    events = [
        Event(
            type="generation",
            messages=[{"role": "user", "content": "q"}],
            calls=[
                {
                    "id": "c0",
                    "type": "function",
                    "function": {"name": "a", "arguments": "{}"},
                },
                {
                    "id": "c1",
                    "type": "function",
                    "function": {"name": "b", "arguments": "{}"},
                },
            ],
        ),
        Event(type="tool_result", call_id="c0", name="a", result="done"),
    ]
    assert [m["role"] for m in replay_messages(events)] == ["user"]


@pytest.mark.asyncio
async def test_resume_recovers_from_a_crash_between_call_and_result():
    store = MemoryStore()
    run_id = "r1"
    for event in [
        Event(type="run_start", messages=[{"role": "user", "content": "weather?"}]),
        Event(
            type="generation",
            messages=[{"role": "user", "content": "weather?"}],
            calls=[
                {
                    "id": "c0",
                    "type": "function",
                    "function": {"name": "weather", "arguments": '{"city": "Oslo"}'},
                }
            ],
        ),
        Event(type="tool_call", name="weather", call_id="c0"),
    ]:
        store.append(run_id, event)

    model = FakeModel(calls(("weather", '{"city": "Oslo"}')), text("sunny"))
    result = await AgentLoop(model=model, tools=[weather], store=store).aresume(run_id)

    assert result.final_output == "sunny"
    # the tool actually ran on resume rather than being skipped
    assert any(
        e.type == "tool_result" and e.result == "Oslo: sunny" for e in result.events
    )


# ------------------------------------------------ P1: MCP state across runs


def make_server(session):
    class Server(MCPServer):
        connects = 0
        closes = 0

        async def connect(self):
            Server.connects += 1
            self._session = session
            return await self.list_tools()

        async def close(self):
            Server.closes += 1

    return Server


@pytest.mark.asyncio
async def test_concurrent_runs_do_not_share_mcp_tool_state():
    """Two runs on one loop must not strip each other's remote tools."""
    Server = make_server(
        FakeSession([remote_tool("remote")], results={"remote": "hit"})
    )
    loop = AgentLoop(
        model=FakeModel(),
        tools=[weather],
        mcp_servers=[Server("http://example/mcp")],
    )

    async def one():
        model = FakeModel(calls(("remote", "{}")), text("ok"))
        loop_copy = loop.with_model(model)
        result = await loop_copy.arun("go")
        return [e.result for e in result.events if e.type == "tool_result"]

    results = await asyncio.gather(*(one() for _ in range(6)))

    assert all(r == ["hit"] for r in results), (
        f"a concurrent run lost its remote tool: {results}"
    )
    # the shared loop's own tool map is never mutated
    assert sorted(loop.tools) == ["weather"]
    assert Server.connects == Server.closes


@pytest.mark.asyncio
async def test_each_run_gets_its_own_server_instance():
    """Sharing one live session across runs lets the first finisher close it."""
    Server = make_server(FakeSession([remote_tool("remote")]))
    template = Server("http://example/mcp")
    loop = AgentLoop(model=FakeModel(text("x")), mcp_servers=[template])

    await loop.arun("go")
    assert template._session is None, "the template must stay unconnected"


@pytest.mark.asyncio
async def test_mcp_transport_is_closed_when_discovery_fails(monkeypatch):
    """If list_tools raises after connecting, the transport must not leak.

    Exercises the real `connect()` against a faked transport rather than
    reimplementing its logic here.
    """
    import contextlib

    import mcp
    import mcp.client.streamable_http as streamable

    closed = []

    @contextlib.asynccontextmanager
    async def fake_transport(url, headers=None, timeout=None, **kwargs):
        try:
            yield (object(), object(), None)
        finally:
            closed.append("transport")

    @contextlib.asynccontextmanager
    async def fake_session(read, write):
        session = type(
            "S", (), {"initialize": lambda self: asyncio.sleep(0)}
        )()
        try:
            yield session
        finally:
            closed.append("session")

    monkeypatch.setattr(streamable, "streamablehttp_client", fake_transport)
    monkeypatch.setattr(mcp, "ClientSession", fake_session)

    class Failing(MCPServer):
        async def list_tools(self):
            raise RuntimeError("discovery exploded")

    server = Failing("http://example/mcp")
    with pytest.raises(RuntimeError, match="discovery exploded"):
        await server.connect()

    assert closed == ["session", "transport"], "the opened transport must be closed"
    assert server._stack is None and server._session is None


# ------------------------------------------------ P2: failure tracing


class RecordingTracer:
    def __init__(self):
        self.exported = []

    def collector(self, workflow_name, **kwargs):
        from agentor.engine.tracing import TraceCollector

        return TraceCollector(workflow_name, **kwargs)

    def export(self, collector):
        self.exported.append(collector.items)


@pytest.mark.asyncio
async def test_a_failed_run_is_still_traced():
    """The runs worth tracing most are the ones that broke."""
    tracer = RecordingTracer()
    loop = AgentLoop(model=Boom("kaboom"), tracer=tracer)

    with pytest.raises(RuntimeError):
        await loop.arun("go")

    (items,) = tracer.exported
    agent_span = next(i for i in items[1:] if i["span_data"]["type"] == "agent")
    assert agent_span["span_data"]["status"] == "failed"
    assert "kaboom" in agent_span["error"]["message"]


@pytest.mark.asyncio
async def test_a_failed_run_gets_a_terminal_event_in_the_log():
    """Without one, a crashed run is indistinguishable from one still running."""
    store = MemoryStore()
    with pytest.raises(RuntimeError):
        await AgentLoop(model=Boom(), store=store).arun("go")

    (run_id,) = store.list_runs()
    end = [e for e in store.load(run_id) if e.type == "run_end"]
    assert len(end) == 1
    assert end[0].status == "failed"


# ------------------------------------------------ P2: strict json schema


class Nested(BaseModel):
    z: int


class Optionals(BaseModel):
    a: str
    b: Optional[int] = None
    inner: Optional[Nested] = None


def test_strictify_normalizes_nested_objects_and_defs():
    schema = _strictify(Optionals.model_json_schema())

    assert schema["additionalProperties"] is False
    assert sorted(schema["required"]) == ["a", "b", "inner"]

    nested = schema["$defs"]["Nested"]
    assert nested["additionalProperties"] is False, "nested objects need it too"
    assert nested["required"] == ["z"]


@pytest.mark.asyncio
async def test_optional_fields_survive_strict_mode():
    model = FakeModel(text('{"a": "x", "b": null, "inner": null}'))
    result = await AgentLoop(model=model, output_type=Optionals).arun("go")

    assert result.final_output.a == "x"
    assert result.final_output.b is None


# ------------------------------------------------ P2: Agentor plumbing


@pytest.mark.asyncio
async def test_per_call_max_turns_is_honoured():
    model = FakeModel(*[calls(("weather", '{"city": "X"}')) for _ in range(10)])
    loop = AgentLoop(model=model, tools=[weather], max_turns=10)

    result = await loop.arun("go", max_turns=2)
    assert result.status == "max_turns"
    assert "max_turns (2)" in result.error
    assert len(model.calls) == 2


@pytest.mark.asyncio
async def test_agentor_arun_passes_max_turns_to_the_native_engine():
    from agentor import Agentor

    model = FakeModel(*[calls(("weather", '{"city": "X"}')) for _ in range(10)])
    agent = Agentor(
        name="T", model=model, tools=[weather], engine="native", api_key="test"
    )
    result = await agent.arun("go", max_turns=3)

    assert result.status == "max_turns"
    assert len(model.calls) == 3


@pytest.mark.asyncio
async def test_streamed_runs_are_persisted():
    """A streamed run should be as resumable as a non-streamed one."""
    from agentor import Agentor

    store = MemoryStore()
    agent = Agentor(
        name="T",
        model=FakeModel(text("streamed answer")),
        engine="native",
        api_key="test",
        store=store,
    )
    _ = [chunk async for chunk in agent.stream_chat("go", serialize=False)]

    (run_id,) = store.list_runs()
    assert any(e.type == "run_end" for e in store.load(run_id))


@pytest.mark.asyncio
async def test_resume_of_a_completed_run_returns_the_parsed_output_type():
    """resume() must not change return type based on whether it re-ran."""
    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(text('{"a": "x", "b": 1, "inner": null}')),
        output_type=Optionals,
        store=store,
    )
    first = await loop.arun("go")
    assert isinstance(first.final_output, Optionals)

    resumed = await loop.aresume(first.run_id)
    assert isinstance(resumed.final_output, Optionals), (
        "a finished run resumed to a raw JSON string instead of the model"
    )
    assert resumed.final_output.a == "x"


# ------------------------------------------------ P2: FunctionTool context


@pytest.mark.asyncio
async def test_function_tool_adapter_receives_the_run_context():
    """A FunctionTool reading ctx.context lost its credentials under native."""
    from agents import RunContextWrapper, function_tool

    seen = {}

    @function_tool
    async def needs_ctx(wrapper: RunContextWrapper, q: str) -> str:
        """Doc.

        Args:
            q: query.
        """
        seen["context"] = wrapper.context
        return "ok"

    sentinel = object()
    model = FakeModel(calls(("needs_ctx", '{"q": "x"}')), text("done"))
    loop = AgentLoop(model=model, tools=[needs_ctx], context=sentinel)
    await loop.arun("go")

    assert seen["context"] is sentinel
