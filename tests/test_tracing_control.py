"""Per-run control over tracing.

Tracing ships run contents - prompts, tool arguments, tool results - to a
remote endpoint, so whether a given run is traced needs to be answerable per
call, not only when the agent is built.
"""

import pytest

from agentor.engine import AgentLoop
from agentor.engine.tracing import TraceCollector
from tests.test_engine import FakeModel, calls, text, weather


class RecordingTracer:
    def __init__(self):
        self.exported = []

    def collector(self, workflow_name, **kwargs):
        return TraceCollector(workflow_name, **kwargs)

    def export(self, collector):
        self.exported.append(collector.items)


# ------------------------------------------------------------ engine level


@pytest.mark.asyncio
async def test_tracing_defaults_to_the_configured_tracer():
    tracer = RecordingTracer()
    await AgentLoop(model=FakeModel(text("hi")), tracer=tracer).arun("go")
    assert len(tracer.exported) == 1


@pytest.mark.asyncio
async def test_tracing_false_sends_nothing_for_that_run():
    tracer = RecordingTracer()
    loop = AgentLoop(model=FakeModel(text("a"), text("b")), tracer=tracer)

    await loop.arun("traced")
    await loop.arun("private", tracing=False)
    await loop.arun("traced again")

    assert len(tracer.exported) == 2, "the opted-out run must not be exported"


@pytest.mark.asyncio
async def test_tracing_false_does_not_disturb_the_run():
    tracer = RecordingTracer()
    result = await AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}')), text("done")),
        tools=[weather],
        tracer=tracer,
    ).arun("go", tracing=False)

    assert result.final_output == "done"
    assert [e.result for e in result.events if e.type == "tool_result"] == ["X: sunny"]
    assert tracer.exported == []


@pytest.mark.asyncio
async def test_tracing_true_without_a_tracer_is_an_error_not_a_silent_noop():
    loop = AgentLoop(model=FakeModel(text("hi")))
    with pytest.raises(ValueError, match="no tracer is configured"):
        await loop.arun("go", tracing=True)


@pytest.mark.asyncio
async def test_tracing_true_uses_the_configured_tracer():
    tracer = RecordingTracer()
    await AgentLoop(model=FakeModel(text("hi")), tracer=tracer).arun("go", tracing=True)
    assert len(tracer.exported) == 1


@pytest.mark.asyncio
async def test_streaming_honours_the_flag():
    tracer = RecordingTracer()
    loop = AgentLoop(model=FakeModel(text("hi")), tracer=tracer)

    async for _ in loop.astream("go", tracing=False):
        pass

    assert tracer.exported == []


def test_sync_run_honours_the_flag():
    tracer = RecordingTracer()
    AgentLoop(model=FakeModel(text("hi")), tracer=tracer).run("go", tracing=False)
    assert tracer.exported == []


# ------------------------------------------------------------ Agentor level


def native(model, **kwargs):
    from agentor import Agentor

    return Agentor(name="T", model=model, api_key="test", **kwargs)


def test_agentor_run_can_opt_out():
    tracer = RecordingTracer()
    agent = native(FakeModel(text("hi")), tracer=tracer)

    agent.run("private", tracing=False)
    assert tracer.exported == []

    agent.run("traced")
    assert len(tracer.exported) == 1


@pytest.mark.asyncio
async def test_agentor_arun_can_opt_out():
    tracer = RecordingTracer()
    agent = native(FakeModel(text("hi")), tracer=tracer)

    await agent.arun("private", tracing=False)
    assert tracer.exported == []


@pytest.mark.asyncio
async def test_agentor_batch_opt_out_covers_every_prompt():
    """A batch run fans out; the flag has to reach each one."""
    tracer = RecordingTracer()
    agent = native(FakeModel(*[text("x")] * 4), tracer=tracer)

    await agent.arun(["a", "b", "c"], tracing=False)
    assert tracer.exported == []


@pytest.mark.asyncio
async def test_agentor_stream_chat_can_opt_out():
    tracer = RecordingTracer()
    agent = native(FakeModel(text("hi")), tracer=tracer)

    _ = [c async for c in agent.stream_chat("go", serialize=False, tracing=False)]
    assert tracer.exported == []


def test_tracing_true_builds_a_tracer_without_storing_it(monkeypatch):
    """Opting one run in must not enrol every run after it.

    Storing the on-demand tracer on the agent would mean a single
    `tracing=True` call quietly turned tracing on for good - the exact leak
    this API exists to prevent.
    """
    from agentor import config as config_module
    from agentor.engine.tracing import CelestoTracer

    class _Secret:
        def get_secret_value(self):
            return "cel_test"

    monkeypatch.setattr(config_module.celesto_config, "api_key", _Secret())

    agent = native(FakeModel(text("hi")))
    assert agent._loop.tracer is None, "tracing is opt-in"

    resolved = agent._resolve_tracing(True)
    assert isinstance(resolved, CelestoTracer), "the run gets a tracer"
    assert agent._loop.tracer is None, "but the agent does not keep it"


def test_an_opted_in_run_does_not_trace_later_runs(monkeypatch):
    """End-to-end version of the leak: run one traced, the next must not be."""
    from agentor import config as config_module
    from agentor.core import agent as agent_module

    exported = []

    class Cap:
        def collector(self, workflow_name, **kwargs):
            return TraceCollector(workflow_name, **kwargs)

        def export(self, collector):
            exported.append(1)

    class _Secret:
        def get_secret_value(self):
            return "cel_test"

    monkeypatch.setattr(config_module.celesto_config, "api_key", _Secret())
    monkeypatch.setattr(agent_module, "setup_celesto_tracing", lambda **kwargs: Cap())

    agent = native(FakeModel(text("1"), text("2"), text("3")))

    agent.run("trace this one", tracing=True)
    assert exported == [1]

    agent.run("this one should not be traced")
    agent.run("nor this one")
    assert exported == [1], "a one-off opt-in leaked into later runs"


@pytest.mark.asyncio
async def test_a_tracer_object_can_be_passed_for_a_single_run():
    tracer = RecordingTracer()
    loop = AgentLoop(model=FakeModel(text("a"), text("b")))

    await loop.arun("traced", tracing=tracer)
    await loop.arun("not traced")

    assert len(tracer.exported) == 1
    assert loop.tracer is None, "a per-run tracer must not attach to the loop"


def test_tracing_true_without_any_key_explains_itself(monkeypatch):
    from agentor import config as config_module

    monkeypatch.setattr(config_module.celesto_config, "api_key", None)

    agent = native(FakeModel(text("hi")))
    with pytest.raises(ValueError, match="requires a Celesto API key"):
        agent.run("go", tracing=True)
