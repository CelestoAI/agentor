"""Tests for native-engine tracing (agentor.engine.tracing)."""

import pytest
from tests.test_engine import FakeModel, calls, text, weather

from agentor.engine import AgentLoop
from agentor.engine.tracing import CelestoTracer, TraceCollector


class RecordingTracer:
    """Captures what would have been exported instead of sending it."""

    def __init__(self):
        self.exported = []

    def collector(self, workflow_name, **kwargs):
        return TraceCollector(workflow_name, **kwargs)

    def export(self, collector):
        self.exported.append(collector.items)


@pytest.mark.asyncio
async def test_run_produces_a_trace_and_spans():
    tracer = RecordingTracer()
    loop = AgentLoop(
        name="Weather Agent",
        model=FakeModel(calls(("weather", '{"city": "Rome"}')), text("sunny")),
        tools=[weather],
        tracer=tracer,
    )
    await loop.arun("go")

    (items,) = tracer.exported
    kinds = [
        i["object"] if i["object"] == "trace" else i["span_data"]["type"] for i in items
    ]
    assert kinds == ["trace", "generation", "function", "generation", "agent"]

    trace = items[0]
    assert trace["workflow_name"] == "Weather Agent"
    assert trace["id"].startswith("trace_")


@pytest.mark.asyncio
async def test_spans_share_one_trace_and_parent():
    tracer = RecordingTracer()
    loop = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "A"}')), text("done")),
        tools=[weather],
        tracer=tracer,
    )
    await loop.arun("go")
    (items,) = tracer.exported

    trace_id = items[0]["id"]
    spans = items[1:]
    assert {s["trace_id"] for s in spans} == {trace_id}

    agent_span = next(s for s in spans if s["span_data"]["type"] == "agent")
    children = [s for s in spans if s["span_data"]["type"] != "agent"]
    assert agent_span["parent_id"] is None
    assert {s["parent_id"] for s in children} == {agent_span["span_id"]}


@pytest.mark.asyncio
async def test_generation_span_carries_request_and_usage():
    tracer = RecordingTracer()
    loop = AgentLoop(
        model=FakeModel(text("hello")), tracer=tracer, instructions="be nice"
    )
    await loop.arun("hi")

    (items,) = tracer.exported
    generation = next(i for i in items[1:] if i["span_data"]["type"] == "generation")
    data = generation["span_data"]

    assert [m["role"] for m in data["input"]] == ["system", "user"]
    assert data["output"] == "hello"
    assert data["usage"]["total_tokens"] == 3
    assert generation["started_at"] and generation["ended_at"]


@pytest.mark.asyncio
async def test_tool_failure_is_recorded_on_the_span():
    def broken(x: str) -> str:
        """Broken.

        Args:
            x: anything.
        """
        raise RuntimeError("boom")

    tracer = RecordingTracer()
    loop = AgentLoop(
        model=FakeModel(calls(("broken", '{"x": "1"}')), text("gave up")),
        tools=[broken],
        tracer=tracer,
    )
    await loop.arun("go")

    (items,) = tracer.exported
    function_span = next(i for i in items[1:] if i["span_data"]["type"] == "function")
    assert function_span["error"]["message"] == "RuntimeError: boom"
    assert function_span["span_data"]["name"] == "broken"


@pytest.mark.asyncio
async def test_max_turns_is_recorded_as_a_failed_agent_span():
    tracer = RecordingTracer()
    loop = AgentLoop(
        model=FakeModel(*[calls(("weather", '{"city": "X"}')) for _ in range(4)]),
        tools=[weather],
        max_turns=2,
        tracer=tracer,
    )
    await loop.arun("go")

    (items,) = tracer.exported
    agent_span = next(i for i in items[1:] if i["span_data"]["type"] == "agent")
    assert agent_span["span_data"]["status"] == "max_turns"
    assert "max_turns" in agent_span["error"]["message"]


@pytest.mark.asyncio
async def test_broken_tracer_cannot_break_a_run():
    class Exploding:
        def collector(self, *a, **k):
            class C:
                items = [{"x": 1}]

                def handle(self, event):
                    raise RuntimeError("collector is broken")

            return C()

        def export(self, collector):
            raise RuntimeError("export is broken")

    loop = AgentLoop(model=FakeModel(text("fine")), tracer=Exploding())
    result = await loop.arun("go")

    assert result.final_output == "fine"
    assert result.status == "completed"


@pytest.mark.asyncio
async def test_no_tracer_means_no_overhead_path():
    loop = AgentLoop(model=FakeModel(text("fine")))
    assert loop.tracer is None
    assert (await loop.arun("go")).final_output == "fine"


def test_export_swallows_network_errors(monkeypatch):
    tracer = CelestoTracer(
        endpoint="http://127.0.0.1:1/ingest", token="t", timeout=0.01
    )
    collector = TraceCollector("wf")
    collector.items.append({"object": "trace", "id": "trace_1"})

    # unreachable endpoint must not raise into the caller
    tracer.export(collector)


def test_export_skips_when_there_is_nothing_to_send(monkeypatch):
    import httpx

    posts = []
    monkeypatch.setattr(httpx, "post", lambda *a, **k: posts.append(a))

    tracer = CelestoTracer(endpoint="http://example/ingest", token="t")
    tracer.export(TraceCollector("wf"))

    assert posts == [], "an empty collector must not hit the network"


def test_agentor_native_wires_a_tracer_when_configured(monkeypatch):
    from agentor import config as config_module

    monkeypatch.setattr(
        config_module.celesto_config, "api_key", _Secret("cel_test"), raising=False
    )
    monkeypatch.setattr(
        config_module.celesto_config, "disable_auto_tracing", False, raising=False
    )

    from agentor import Agentor

    agent = Agentor(
        name="T", model=FakeModel(text("x")), engine="native", api_key="test"
    )
    assert isinstance(agent._loop.tracer, CelestoTracer)


class _Secret:
    def __init__(self, value):
        self.value = value

    def get_secret_value(self):
        return self.value
