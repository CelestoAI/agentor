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
from agentor.engine.store import MemoryStore, replay_messages, total_usage
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
        session = type("S", (), {"initialize": lambda self: asyncio.sleep(0)})()
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
    agent = Agentor(name="T", model=model, tools=[weather], api_key="test")
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


# ============================================ second review round


@pytest.mark.asyncio
async def test_input_is_persisted_when_mcp_setup_fails():
    """MCP failure happens before the loop starts; the input must survive it."""

    class Unreachable(MCPServer):
        async def connect(self):
            raise ConnectionError("mcp server unreachable")

        async def close(self):
            pass

    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(text("never runs")),
        store=store,
        mcp_servers=[Unreachable("http://example/mcp")],
    )

    with pytest.raises(ConnectionError):
        await loop.arun("do not lose this")

    (run_id,) = store.list_runs()
    events = store.load(run_id)
    assert [e.type for e in events] == ["run_start", "run_end"]
    assert replay_messages(events)[-1]["content"] == "do not lose this"


@pytest.mark.asyncio
async def test_run_is_resumable_after_an_mcp_setup_failure():
    class Unreachable(MCPServer):
        async def connect(self):
            raise ConnectionError("down")

        async def close(self):
            pass

    store = MemoryStore()
    with pytest.raises(ConnectionError):
        await AgentLoop(
            model=FakeModel(),
            store=store,
            mcp_servers=[Unreachable("http://example/mcp")],
        ).arun("question")

    (run_id,) = store.list_runs()
    recovered = await AgentLoop(model=FakeModel(text("ok")), store=store).aresume(
        run_id
    )
    assert recovered.final_output == "ok"


@pytest.mark.asyncio
async def test_invalid_structured_output_is_recorded_as_a_failed_run():
    """The caller saw an exception; the log must not claim success."""
    store = MemoryStore()
    tracer = RecordingTracer()
    loop = AgentLoop(
        model=FakeModel(text("this is not json")),
        output_type=Optionals,
        store=store,
        tracer=tracer,
    )

    with pytest.raises(ValueError, match="did not match Optionals"):
        await loop.arun("go")

    (run_id,) = store.list_runs()
    end = [e for e in store.load(run_id) if e.type == "run_end"]
    assert [e.status for e in end] == ["failed"]

    (items,) = tracer.exported
    agent_span = next(i for i in items[1:] if i["span_data"]["type"] == "agent")
    assert agent_span["span_data"]["status"] == "failed"


def test_mapping_output_types_are_rejected_with_an_explanation():
    """OpenAI strict mode cannot express an open map; fail before the request."""
    from typing import Dict as TDict

    class HasMap(BaseModel):
        a: str
        meta: TDict[str, str] = {}

    with pytest.raises(TypeError, match="dict/mapping field"):
        AgentLoop(model=FakeModel(text("x")), output_type=HasMap)


def test_optional_defaults_are_left_alone():
    """`default: null` is accepted by the API; stripping it would be churn."""
    schema = _strictify(Optionals.model_json_schema())
    assert schema["properties"]["b"]["default"] is None


@pytest.mark.asyncio
async def test_max_turns_is_honoured_for_message_list_input():
    from agentor import Agentor

    model = FakeModel(*[calls(("weather", '{"city": "X"}')) for _ in range(10)])
    agent = Agentor(name="T", model=model, tools=[weather], api_key="test")
    result = await agent.arun([{"role": "user", "content": "go"}], max_turns=2)

    assert result.status == "max_turns"
    assert len(model.calls) == 2


@pytest.mark.asyncio
async def test_connecting_twice_is_refused_rather_than_leaking():
    server = MCPServer("http://example/mcp", name="dup")
    server._stack = object()  # pretend a live connection

    with pytest.raises(RuntimeError, match="already connected"):
        await server.connect()


# ============================================ third review round


@pytest.mark.asyncio
async def test_sync_tools_run_in_parallel():
    """Sync tools called inline serialize every gather and stall the loop."""
    import time as _time

    def slow(x: str) -> str:
        """Slow.

        Args:
            x: anything.
        """
        _time.sleep(0.2)
        return "done"

    model = FakeModel(
        calls(("slow", '{"x": "1"}'), ("slow", '{"x": "2"}'), ("slow", '{"x": "3"}')),
        text("ok"),
    )
    loop = AgentLoop(model=model, tools=[slow])

    started = _time.perf_counter()
    await loop.arun("go")
    elapsed = _time.perf_counter() - started

    assert elapsed < 0.45, f"3x0.2s sync tools took {elapsed:.2f}s - serialized"


@pytest.mark.asyncio
async def test_the_event_loop_stays_responsive_during_a_sync_tool():
    ticks = []

    def blocking(x: str) -> str:
        """Blocks.

        Args:
            x: anything.
        """
        import time as _time

        _time.sleep(0.3)
        return "done"

    async def ticker():
        for _ in range(10):
            await asyncio.sleep(0.02)
            ticks.append(1)

    loop = AgentLoop(
        model=FakeModel(calls(("blocking", '{"x": "1"}')), text("ok")),
        tools=[blocking],
    )
    await asyncio.gather(loop.arun("go"), ticker())

    assert len(ticks) == 10, "the event loop was blocked by a sync tool"


def test_litellm_errors_are_resolved_when_the_error_is_raised():
    """Building the tuple up front misses litellm's lazily imported errors."""
    import sys

    from agentor.core.agent import _is_retryable

    litellm = sys.modules.get("litellm")
    if litellm is None:  # pragma: no cover - depends on import order
        import litellm  # noqa: F811

    assert _is_retryable(litellm.RateLimitError("rate limited", "m", "p")), (
        "a litellm rate limit must trigger the configured fallbacks"
    )


def test_usage_spans_resumed_segments():
    """A resumed run has one run_end per segment; the last one is partial."""
    from agentor.engine.events import Usage

    events = [
        Event(type="generation", usage=Usage(10, 20, 30)),
        Event(type="run_end", status="max_turns", usage=Usage(10, 20, 30)),
        Event(type="generation", usage=Usage(1, 2, 3)),
        Event(type="run_end", status="completed", usage=Usage(1, 2, 3)),
    ]
    assert total_usage(events) == Usage(11, 22, 33)


@pytest.mark.asyncio
async def test_resumed_result_reports_total_usage():
    store = MemoryStore()
    first = await AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    ).arun("go")

    await AgentLoop(
        model=FakeModel(text("done")), tools=[weather], store=store
    ).aresume(first.run_id)
    resumed = await AgentLoop(model=FakeModel(), store=store).aresume(first.run_id)

    assert resumed.usage.total_tokens == 6, "usage before the resume was dropped"


def test_cross_loop_close_leaves_the_connection_recoverable():
    """Clearing state before raising would strand the live transport."""
    server = MCPServer("http://example/mcp", name="x")
    stack = object()

    async def pretend_connected():
        server._loop = asyncio.get_running_loop()
        server._stack = stack
        server._session = object()

    asyncio.run(pretend_connected())

    async def close_from_another_loop():
        with pytest.raises(RuntimeError, match="different event loop"):
            await server.close()

    asyncio.run(close_from_another_loop())
    assert server._stack is stack, "state must survive so cleanup can be retried"
    assert server._session is not None


# ============================================ multi-provider entry point


def test_base_url_routes_to_the_chat_completions_adapter():
    """The multi-provider story is unusable if base_url isn't on the public API."""
    from agentor import Agentor
    from agentor.engine.models import ChatCompletionsModel

    agent = Agentor(
        name="T",
        model="openrouter/auto",
        base_url="https://openrouter.ai/api/v1",
        api_key="test",
    )
    assert isinstance(agent._loop.model, ChatCompletionsModel)
    assert agent._loop.model.model == "openrouter/auto"


def test_provider_prefixed_model_still_routes_to_litellm_without_base_url():
    from agentor import Agentor
    from agentor.engine.models import LiteLLMModel

    agent = Agentor(name="T", model="gemini/gemini-2.0-flash", api_key="test")
    assert isinstance(agent._loop.model, LiteLLMModel)


def test_model_settings_reach_the_native_model():
    from agentor import Agentor, ModelSettings

    agent = Agentor(
        name="T",
        model="gpt-4o-mini",
        api_key="test",
        engine="native",
        model_settings=ModelSettings(temperature=0.2, max_tokens=400),
    )
    assert agent._loop.model.params["temperature"] == 0.2
    assert agent._loop.model.params["max_tokens"] == 400


# ============================================ unrunnable tool objects


class HostedTool:
    """Shaped like a provider-hosted tool: a name, nothing to invoke."""

    name = "web_search"


class LocalRunnerTool:
    """An SDK tool executed by its own runner - the same shape, run locally."""

    name = "local_shell"


def test_unrunnable_tools_fail_with_an_actionable_message():
    """A generic 'unsupported type' hides why a documented tool stopped working."""
    from agentor.engine.tools import resolve_tools

    with pytest.raises(TypeError, match="no callable to invoke") as exc:
        resolve_tools([HostedTool()])

    message = str(exc.value)
    assert "web_search" in message
    assert "function tool" in message


def test_the_message_does_not_assert_the_wrong_execution_model():
    """Locally executed SDK tools share the shape of provider-hosted ones.

    A message blaming OpenAI's Responses API would send the reader looking in
    entirely the wrong place for a tool that runs on their own machine.
    """
    from agentor.engine.tools import resolve_tools

    with pytest.raises(TypeError) as exc:
        resolve_tools([LocalRunnerTool()])

    message = str(exc.value)
    assert "local_shell" in message
    assert "Responses API" not in message


def test_agentor_surfaces_the_unrunnable_tool_message():
    from agentor import Agentor

    with pytest.raises(TypeError, match="no callable to invoke"):
        Agentor(name="T", model="gpt-4o-mini", tools=[HostedTool()], api_key="test")


# ============================================ openai-agents removal review


def test_default_model_is_unchanged_by_the_removal():
    """Changing the default silently alters quality and billing."""
    import inspect

    from agentor import Agentor

    assert inspect.signature(Agentor.__init__).parameters["model"].default == (
        "gpt-5-nano"
    )


def test_from_md_default_matches_the_constructor_default(tmp_path):
    from agentor import Agentor

    md = tmp_path / "a.md"
    md.write_text("---\nname: Bot\n---\nYou are helpful.")
    agent = Agentor.from_md(md, api_key="test")
    assert agent._loop.model.model == "gpt-5-nano"


@pytest.mark.asyncio
async def test_fallback_keeps_the_configured_model_parameters():
    """A fallback that drops temperature answers differently to the primary."""
    import httpx
    import openai

    from agentor import Agentor, ModelSettings

    response = httpx.Response(
        429, request=httpx.Request("POST", "https://api.openai.com/v1/chat")
    )
    captured = {}

    agent = Agentor(
        name="T",
        model="gpt-4o-mini",
        api_key="test",
        model_settings=ModelSettings(temperature=0.2, max_tokens=64),
    )

    async def boom(*a, **k):
        raise openai.RateLimitError("rate limited", response=response, body=None)

    agent._loop.model.complete = boom

    original_with_model = agent._loop.with_model

    def spy(model, **kwargs):
        captured.update(kwargs)
        clone = original_with_model(model, **kwargs)
        clone.model = FakeModel(text("from fallback"))
        return clone

    agent._loop.with_model = spy
    result = await agent.arun("go", fallback_models=["gpt-4o"])

    assert result.final_output == "from fallback"
    assert captured["temperature"] == 0.2
    assert captured["max_tokens"] == 64


def test_model_settings_accepts_previously_exported_fields():
    """Rejecting them would break settings written against the old type."""
    from agentor import ModelSettings

    settings = ModelSettings(
        temperature=0.5,
        tool_choice="auto",
        parallel_tool_calls=True,
        verbosity="low",
        some_provider_flag=1,
    )
    params = settings.to_params()
    assert params["tool_choice"] == "auto"
    assert params["parallel_tool_calls"] is True
    assert params["some_provider_flag"] == 1, "unknown keys should pass through"


def test_model_settings_drops_parameters_with_no_equivalent(caplog):
    from agentor import ModelSettings

    with caplog.at_level("WARNING"):
        params = ModelSettings(temperature=0.1, truncation="auto").to_params()

    assert "truncation" not in params, "forwarding it would earn a provider 400"
    assert "truncation" in caplog.text


def test_function_tool_accepts_legacy_decorator_options():
    """@function_tool(strict_mode=False) must not fail at import time."""
    from agentor import function_tool

    @function_tool(strict_mode=False, use_docstring_info=True)
    def greet(name: str) -> str:
        """Greet.

        Args:
            name: who.
        """
        return name

    assert greet.name == "greet"


def test_run_context_is_subscriptable():
    """Tools were commonly annotated RunContextWrapper[Config]."""
    from agentor.engine.tools import RunContext, build_schema

    def fn(ctx: RunContext[dict], q: str) -> str:
        """Doc.

        Args:
            q: query.
        """
        return q

    _, schema, context_param = build_schema(fn)
    assert context_param == "ctx"
    assert list(schema["properties"]) == ["q"]


def test_agentor_accepts_an_explicit_tracer():
    """setup_celesto_tracing documents handing its result to Agentor."""
    from agentor import Agentor
    from agentor.tracer import setup_celesto_tracing

    tracer = setup_celesto_tracing(endpoint="http://example/ingest", token="t")
    agent = Agentor(name="T", model="gpt-4o-mini", api_key="test", tracer=tracer)
    assert agent._loop.tracer is tracer


# ============================================ whole-line review


def test_version_is_a_valid_prerelease():
    """The 0.1.0 line ships as a prerelease on purpose.

    pip excludes prereleases by default, which is exactly what is wanted: this
    release drops a dependency, removes DurableAgent and drops hosted tools, so
    `pip install --upgrade agentor` must not sweep 0.0.x users into it. They
    opt in with --pre or an explicit pin.

    The phase may advance a -> b -> rc without touching this test; going stable
    is a deliberate decision that should have to change it.
    """
    from packaging.version import Version

    import agentor

    version = Version(agentor.__version__)
    assert version.is_prerelease, (
        f"{agentor.__version__} is stable; upgrading 0.0.x users into a "
        "breaking release should be an explicit choice"
    )
    assert version.base_version == "0.1.0"
    assert version.pre[0] in ("a", "b", "rc"), agentor.__version__


def test_the_previous_mcp_import_still_works():
    """0.0.22 code must not fail at import before it can read a migration note."""
    import warnings

    from agentor.mcp import MCPServer, MCPServerStreamableHttp

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        server = MCPServerStreamableHttp(
            name="x",
            params={"url": "http://e/mcp", "headers": {"A": "b"}, "timeout": 10},
            cache_tools_list=True,
            max_retry_attempts=3,
        )

    assert isinstance(server, MCPServer)
    assert server.url == "http://e/mcp"
    assert server.headers == {"A": "b"}
    assert any(w.category is DeprecationWarning for w in caught)


def test_the_old_mcp_shim_rejects_a_missing_url():
    from agentor.mcp import MCPServerStreamableHttp

    with pytest.raises(ValueError, match="requires params"):
        MCPServerStreamableHttp(name="x", params={})


@pytest.mark.asyncio
async def test_run_result_carries_the_conversation():
    """RunResult.messages is documented as resumable context; it must contain it."""
    model = FakeModel(calls(("weather", '{"city": "Oslo"}')), text("sunny"))
    result = await AgentLoop(model=model, tools=[weather], instructions="sys").arun(
        "weather?"
    )

    roles = [m["role"] for m in result.messages]
    assert roles == ["system", "user", "assistant", "tool", "assistant"]
    assert result.messages[-1]["content"] == "sunny"


@pytest.mark.asyncio
async def test_resume_does_not_duplicate_the_system_prompt():
    """replay already returns the system message; prepending sends it twice."""
    store = MemoryStore()
    first = await AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
        instructions="SYSTEM PROMPT",
    ).arun("go")

    model = FakeModel(text("done"))
    await AgentLoop(
        model=model, tools=[weather], store=store, instructions="SYSTEM PROMPT"
    ).aresume(first.run_id)

    roles = [m["role"] for m in model.calls[0]["messages"]]
    assert roles.count("system") == 1, f"duplicated system prompt: {roles}"


@pytest.mark.asyncio
async def test_a_supplied_system_message_is_not_duplicated():
    model = FakeModel(text("ok"))
    await AgentLoop(model=model, instructions="AGENT").arun(
        [{"role": "system", "content": "CALLER"}, {"role": "user", "content": "hi"}]
    )

    messages = model.calls[0]["messages"]
    assert [m["role"] for m in messages] == ["system", "user"]
    assert messages[0]["content"] == "CALLER", "the caller's system message wins"


@pytest.mark.asyncio
async def test_arun_respects_the_constructor_turn_budget():
    """run() honoured it while arun() silently overrode it with its default."""
    from agentor import Agentor

    model = FakeModel(*[calls(("weather", '{"city": "X"}')) for _ in range(10)])
    agent = Agentor(name="T", model=model, tools=[weather], api_key="test", max_turns=3)
    result = await agent.arun("go")

    assert result.status == "max_turns"
    assert len(model.calls) == 3
