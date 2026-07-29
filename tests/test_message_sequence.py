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

from collections import Counter
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import pytest

from agentor.engine import AgentLoop
from tests.test_engine import FakeModel, calls, text

#: one entry of the OpenAI-shaped message list handed to a provider
Message = Dict[str, Any]
#: (tool_name, json_arguments), as accepted by tests.test_engine.calls
ToolSpec = Tuple[str, str]


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


def assert_well_formed(messages: Sequence[Message]) -> None:
    """Every assistant tool_calls turn is answered exactly once, contiguously.

    Compares multisets rather than draining a pending set: a duplicate reply to
    one id, or a reply to an id that was never requested, is as invalid as a
    missing one, and `set.discard` accepts both silently.
    """
    for index, message in enumerate(messages):
        if message.get("role") != "assistant" or not message.get("tool_calls"):
            continue

        expected: Counter = Counter(call["id"] for call in message["tool_calls"])
        observed: Counter = Counter()

        cursor = index + 1
        while cursor < len(messages) and messages[cursor]["role"] == "tool":
            observed[messages[cursor]["tool_call_id"]] += 1
            cursor += 1

        assert observed == expected, (
            f"tool replies did not match the calls: missing "
            f"{sorted((expected - observed).elements())}, unexpected "
            f"{sorted((observed - expected).elements())}; "
            f"sequence was {[m['role'] for m in messages]}"
        )


async def sequence_sent_to_model(
    specs: Sequence[ToolSpec],
    budget: int,
    turns: int,
    tools: Optional[Sequence[Callable[..., str]]] = None,
) -> List[Message]:
    """Run the loop and return the message list from the final request.

    `tools` defaults to the two defined above; pass it when a spec names
    something else, or the call silently becomes an unknown-tool call and
    exercises a different path than the test intends.
    """
    model = FakeModel(*([calls(*specs)] * turns), text("done"))
    loop = AgentLoop(
        model=model,
        tools=list(tools if tools is not None else (broken, working)),
        max_tool_failures=budget,
    )
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


@pytest.mark.asyncio
async def test_a_hallucinated_tool_name_is_bounded_by_the_budget():
    """An unknown name used to bypass the budget and burn every turn."""
    model = FakeModel(*[calls(("ghost", "{}")) for _ in range(10)])
    loop = AgentLoop(model=model, tools=[working], max_turns=10, max_tool_failures=2)
    result = await loop.arun("go")

    errors = [e.error for e in result.events if e.type == "tool_result"]
    assert errors.count("unknown tool") == 2, (
        f"the budget did not engage; errors were {errors}"
    )
    assert any(
        m["role"] == "user" and "'ghost'" in m["content"]
        for m in model.calls[-1]["messages"]
    ), "the model was never told to stop calling it"
