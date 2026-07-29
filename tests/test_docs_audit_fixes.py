"""Regression tests for gaps found while writing the v0.1.0 documentation.

Each was a capability the engine had but no caller could reach, or a number
the API reported wrongly - the kind of thing that surfaces when someone tries
to write an accurate example rather than read the code.
"""

import pytest

from agentor import Agentor
from agentor.engine import AgentLoop
from agentor.engine.store import MemoryStore, total_usage
from agentor.engine.tracing import TraceCollector
from tests.test_engine import FakeModel, calls, text, weather


class CapturingTracer:
    def __init__(self):
        self.collector_kwargs = None
        self.exported = []

    def collector(self, workflow_name, **kwargs):
        self.collector_kwargs = kwargs
        return TraceCollector(workflow_name, **kwargs)

    def export(self, collector):
        self.exported.append(collector.items)


# ------------------------------------------------ max_tool_failures


def test_max_tool_failures_is_reachable_from_agentor():
    """The loop had the budget; Agentor never forwarded it."""
    agent = Agentor(name="T", model="gpt-4o-mini", api_key="test", max_tool_failures=5)
    assert agent._loop.max_tool_failures == 5


def test_max_tool_failures_defaults_to_two():
    agent = Agentor(name="T", model="gpt-4o-mini", api_key="test")
    assert agent._loop.max_tool_failures == 2


@pytest.mark.asyncio
async def test_a_raised_budget_actually_allows_more_attempts():
    executions = []

    def flaky(x: str) -> str:
        """Flaky.

        Args:
            x: anything.
        """
        executions.append(x)
        raise RuntimeError("boom")

    agent = Agentor(
        name="T",
        model=FakeModel(
            calls(("flaky", '{"x": "1"}')),
            calls(("flaky", '{"x": "2"}')),
            calls(("flaky", '{"x": "3"}')),
            text("giving up"),
        ),
        tools=[flaky],
        api_key="test",
        max_tool_failures=3,
    )
    await agent.arun("go")

    assert executions == ["1", "2", "3"], "the configured budget was not applied"


# ------------------------------------------------ trace grouping


def test_trace_group_id_and_metadata_reach_the_collector():
    """TraceCollector accepted them, but astream never passed them."""
    tracer = CapturingTracer()
    agent = Agentor(
        name="T",
        model=FakeModel(text("hi")),
        api_key="test",
        tracer=tracer,
        trace_group_id="session-42",
        trace_metadata={"env": "prod"},
    )
    agent.run("go")

    assert tracer.collector_kwargs == {
        "group_id": "session-42",
        "metadata": {"env": "prod"},
    }


def test_trace_grouping_lands_on_the_exported_trace():
    tracer = CapturingTracer()
    AgentLoop(
        model=FakeModel(text("hi")),
        tracer=tracer,
        trace_group_id="session-7",
        trace_metadata={"tenant": "acme"},
    ).run("go")

    (items,) = tracer.exported
    trace = items[0]
    assert trace["object"] == "trace"
    assert trace["group_id"] == "session-7"
    assert trace["metadata"] == {"tenant": "acme"}


def test_grouping_is_optional():
    tracer = CapturingTracer()
    AgentLoop(model=FakeModel(text("hi")), tracer=tracer).run("go")

    (items,) = tracer.exported
    assert items[0]["group_id"] is None


# ------------------------------------------------ resumed usage


@pytest.mark.asyncio
async def test_a_resumed_run_reports_what_the_whole_run_cost():
    """The continuation's run_end counts only its own generations."""
    store = MemoryStore()
    first = await AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    ).arun("go")

    resumed = await AgentLoop(
        model=FakeModel(text("done")), tools=[weather], store=store
    ).aresume(first.run_id)

    logged = total_usage(store.load(first.run_id))
    assert resumed.usage.total_tokens == logged.total_tokens
    assert resumed.usage.total_tokens > first.usage.total_tokens, (
        "a resumed run that costs more than the first attempt must say so"
    )


@pytest.mark.asyncio
async def test_resuming_a_finished_run_reports_its_full_cost():
    store = MemoryStore()
    first = await AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}')), text("done")),
        tools=[weather],
        store=store,
    ).arun("go")

    resumed = await AgentLoop(model=FakeModel(), store=store).aresume(first.run_id)
    assert resumed.usage.total_tokens == first.usage.total_tokens


def test_sync_resume_reports_total_usage():
    store = MemoryStore()
    loop = AgentLoop(
        model=FakeModel(calls(("weather", '{"city": "X"}'))),
        tools=[weather],
        store=store,
        max_turns=1,
    )
    first = loop.run("go")

    resumed = AgentLoop(
        model=FakeModel(text("done")), tools=[weather], store=store
    ).resume(first.run_id)

    assert (
        resumed.usage.total_tokens == total_usage(store.load(first.run_id)).total_tokens
    )
