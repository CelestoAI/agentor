"""The message list handed to the provider must always be well-formed.

An assistant turn carrying `tool_calls` has to be followed directly by one
`tool` message per call. Anything inserted in between - however sensible its
content - makes the request invalid, and providers reject it outright rather
than degrading.

Reported against 0.1.0a2: the tool failure budget appended its "tool is now
unavailable" notice from inside the loop over results, so a tool exhausting its
budget while siblings were still pending split the run of tool messages. The
feature meant to keep a run alive was ending it.
"""

import pytest

from agentor.engine import AgentLoop
from tests.test_engine import FakeModel, calls, text


def broken(x: str) -> str:
    """Always fails.

    Args:
        x: anything.
    """
    raise RuntimeError("backend down")


def working(x: str) -> str:
    """Always works.

    Args:
        x: anything.
    """
    return "fine"


def assert_well_formed(messages):
    """Every assistant tool_calls turn is answered contiguously."""
    for index, message in enumerate(messages):
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            continue

        pending = {call["id"] for call in message["tool_calls"]}
        cursor = index + 1
        while cursor < len(messages) and messages[cursor]["role"] == "tool":
            pending.discard(messages[cursor]["tool_call_id"])
            cursor += 1

        assert not pending, (
            f"tool_call_ids {sorted(pending)} were not answered contiguously; "
            f"sequence was {[m['role'] for m in messages]}"
        )


async def sequence_sent_to_model(specs, budget, turns):
    """Run the loop and return the message list from the final request."""
    model = FakeModel(*([calls(*specs)] * turns), text("done"))
    loop = AgentLoop(model=model, tools=[broken, working], max_tool_failures=budget)
    await loop.arun("go")
    return model.calls[-1]["messages"]


@pytest.mark.asyncio
async def test_failing_tool_first_of_two_parallel_calls():
    messages = await sequence_sent_to_model(
        [("broken", '{"x": "1"}'), ("working", '{"x": "2"}')], budget=1, turns=1
    )
    assert_well_formed(messages)


@pytest.mark.asyncio
async def test_failing_tool_last_of_two_parallel_calls():
    messages = await sequence_sent_to_model(
        [("working", '{"x": "1"}'), ("broken", '{"x": "2"}')], budget=1, turns=1
    )
    assert_well_formed(messages)


@pytest.mark.asyncio
async def test_budget_exhausted_in_the_middle_of_three_calls():
    messages = await sequence_sent_to_model(
        [
            ("working", '{"x": "1"}'),
            ("broken", '{"x": "2"}'),
            ("working", '{"x": "3"}'),
        ],
        budget=1,
        turns=1,
    )
    assert_well_formed(messages)


@pytest.mark.asyncio
async def test_flaky_tool_retried_beside_a_working_one_on_the_default_budget():
    """The ordinary case, and the one that fired on the default budget."""
    messages = await sequence_sent_to_model(
        [("broken", '{"x": "1"}'), ("working", '{"x": "2"}')], budget=2, turns=2
    )
    assert_well_formed(messages)


@pytest.mark.asyncio
async def test_two_tools_exhaust_their_budgets_in_the_same_turn():
    def alsobroken(x: str) -> str:
        """Also fails.

        Args:
            x: anything.
        """
        raise RuntimeError("also down")

    model = FakeModel(
        calls(("broken", '{"x": "1"}'), ("alsobroken", '{"x": "2"}')),
        text("done"),
    )
    loop = AgentLoop(model=model, tools=[broken, alsobroken], max_tool_failures=1)
    await loop.arun("go")

    messages = model.calls[-1]["messages"]
    assert_well_formed(messages)
    notices = [
        m
        for m in messages
        if m["role"] == "user" and "is now unavailable" in m["content"]
    ]
    assert len(notices) == 2, "each disabled tool should be announced"


@pytest.mark.asyncio
async def test_the_notice_still_reaches_the_model():
    """Deferring the notice must not drop it."""
    messages = await sequence_sent_to_model(
        [("broken", '{"x": "1"}'), ("working", '{"x": "2"}')], budget=1, turns=1
    )
    assert any(
        m["role"] == "user" and "'broken' failed" in m["content"] for m in messages
    )


@pytest.mark.asyncio
async def test_a_healthy_run_is_unaffected():
    messages = await sequence_sent_to_model(
        [("working", '{"x": "1"}'), ("working", '{"x": "2"}')], budget=2, turns=1
    )
    assert_well_formed(messages)
    assert not [
        m for m in messages if m["role"] == "user" and "unavailable" in m["content"]
    ]


@pytest.mark.asyncio
async def test_the_run_completes_rather_than_raising():
    """The point of the budget: a misbehaving tool must not end the run."""
    model = FakeModel(
        calls(("broken", '{"x": "1"}'), ("working", '{"x": "2"}')),
        text("answered without the broken tool"),
    )
    result = await AgentLoop(
        model=model, tools=[broken, working], max_tool_failures=1
    ).arun("go")

    assert result.status == "completed"
    assert result.final_output == "answered without the broken tool"
