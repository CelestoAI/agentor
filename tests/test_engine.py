"""Tests for the native engine (agentor.engine).

The loop is exercised against a scripted fake model so behaviour is asserted
without network access.
"""

from typing import Literal, Optional

import pytest

from agentor.engine import AgentLoop, Tool, resolve_tools
from agentor.engine.events import Usage
from agentor.engine.models import ModelResponse, StreamChunk, ToolCall
from agentor.engine.tools import build_schema, parse_docstring
from agentor.tools.base import BaseTool, capability

# --------------------------------------------------------------- fake model


class FakeModel:
    """Replays a scripted list of ModelResponses and records what it was sent."""

    model = "fake-model"

    def __init__(self, *responses: ModelResponse):
        self.responses = list(responses)
        self.calls = []

    async def complete(self, messages, tools=None):
        self.calls.append({"messages": [dict(m) for m in messages], "tools": tools})
        if not self.responses:
            return ModelResponse(content="done")
        return self.responses.pop(0)

    async def stream(self, messages, tools=None):
        response = await self.complete(messages, tools)
        for piece in (response.content or "").split(" "):
            yield StreamChunk(delta=piece + " ")
        yield StreamChunk(final=response)


def text(content):
    return ModelResponse(content=content, usage=Usage(1, 2, 3))


def calls(*specs):
    return ModelResponse(
        tool_calls=[
            ToolCall(id=f"c{i}", name=name, arguments=args)
            for i, (name, args) in enumerate(specs)
        ],
        usage=Usage(1, 2, 3),
    )


# --------------------------------------------------------------- docstrings


def test_parse_docstring_google_style():
    summary, params = parse_docstring(
        """Do a thing.

        Args:
            a: First value.
            b (int): Second value,
                continued on the next line.

        Returns:
            Something.
        """
    )
    assert summary == "Do a thing."
    assert params["a"] == "First value."
    assert params["b"] == "Second value, continued on the next line."


def test_parse_docstring_empty():
    assert parse_docstring(None) == ("", {})
    assert parse_docstring("") == ("", {})


def test_build_schema_types_and_descriptions():
    def fn(city: str, unit: Literal["c", "f"] = "c", days: Optional[int] = None):
        """Look up weather.

        Args:
            city: Which city.
            unit: Temperature unit.
        """

    description, schema, context_param = build_schema(fn)

    assert description == "Look up weather."
    assert context_param is None
    assert schema["required"] == ["city"]
    assert schema["properties"]["unit"]["enum"] == ["c", "f"]
    assert schema["properties"]["city"]["description"] == "Which city."
    # titles are pydantic noise and are sent on every request
    assert "title" not in schema["properties"]["city"]


def test_build_schema_detects_context_param():
    def fn(wrapper: "RunContextWrapper[str]", city: str):  # noqa: F821
        """Doc."""

    _, schema, context_param = build_schema(fn)
    assert context_param == "wrapper"
    assert list(schema["properties"]) == ["city"]


# --------------------------------------------------------------- tool resolve


def test_resolve_plain_function():
    def greet(name: str) -> str:
        """Greet someone."""
        return f"hi {name}"

    (tool,) = resolve_tools([greet])
    assert tool.name == "greet"
    assert tool.description == "Greet someone."
    assert tool.to_openai()["function"]["name"] == "greet"


def test_resolve_base_tool_capabilities():
    class Multi(BaseTool):
        name = "multi"

        @capability
        def alpha(self, x: str) -> str:
            """Alpha."""
            return f"a{x}"

        @capability
        def beta(self, y: int) -> str:
            """Beta."""
            return f"b{y}"

    tools = {t.name: t for t in resolve_tools([Multi()])}
    assert set(tools) == {"alpha", "beta"}


def test_resolve_registry_name():
    (tool,) = resolve_tools(["current_datetime"])
    assert tool.name == "current_datetime"
    assert tool.context_param == "wrapper"


def test_resolve_rejects_unknown_type():
    with pytest.raises(TypeError, match="Unsupported tool type"):
        resolve_tools([object()])


@pytest.mark.asyncio
async def test_tool_call_stringifies_non_str():
    tool = Tool.from_function(lambda: {"a": 1}, name="t")
    assert await tool.call({}) == '{"a": 1}'


# --------------------------------------------------------------- the loop


def weather(city: str) -> str:
    """Weather.

    Args:
        city: city.
    """
    return f"{city}: sunny"


@pytest.mark.asyncio
async def test_loop_returns_text_without_tools():
    loop = AgentLoop(model=FakeModel(text("hello")), instructions="sys")
    result = await loop.arun("hi")

    assert result.final_output == "hello"
    assert result.status == "completed"
    assert result.usage.total_tokens == 3


@pytest.mark.asyncio
async def test_loop_executes_tool_then_answers():
    model = FakeModel(calls(("weather", '{"city": "Oslo"}')), text("It is sunny."))
    loop = AgentLoop(model=model, tools=[weather])
    result = await loop.arun("weather in Oslo?")

    assert result.final_output == "It is sunny."
    tool_results = [e for e in result.events if e.type == "tool_result"]
    assert [e.result for e in tool_results] == ["Oslo: sunny"]

    # the tool result must be fed back as a `tool` message keyed by call id
    second_request = model.calls[1]["messages"]
    assert second_request[-1]["role"] == "tool"
    assert second_request[-1]["tool_call_id"] == "c0"


@pytest.mark.asyncio
async def test_loop_runs_parallel_tool_calls():
    model = FakeModel(
        calls(("weather", '{"city": "A"}'), ("weather", '{"city": "B"}')),
        text("both done"),
    )
    loop = AgentLoop(model=model, tools=[weather])
    result = await loop.arun("two cities")

    results = [e.result for e in result.events if e.type == "tool_result"]
    assert results == ["A: sunny", "B: sunny"]


@pytest.mark.asyncio
async def test_loop_reports_unknown_tool_without_crashing():
    model = FakeModel(calls(("nope", "{}")), text("recovered"))
    loop = AgentLoop(model=model, tools=[weather])
    result = await loop.arun("go")

    (event,) = [e for e in result.events if e.type == "tool_result"]
    assert event.error == "unknown tool"
    assert "Available tools: weather" in event.result
    assert result.final_output == "recovered"


@pytest.mark.asyncio
async def test_loop_handles_malformed_arguments():
    model = FakeModel(calls(("weather", "{not json")), text("recovered"))
    loop = AgentLoop(model=model, tools=[weather])
    result = await loop.arun("go")

    (event,) = [e for e in result.events if e.type == "tool_result"]
    assert "Invalid JSON" in event.error
    assert result.final_output == "recovered"


@pytest.mark.asyncio
async def test_failing_tool_is_disabled_after_budget():
    """A tool that always raises must not consume every turn."""

    executions = []

    def flaky(x: str) -> str:
        """Flaky.

        Args:
            x: anything.
        """
        executions.append(x)
        raise RuntimeError("boom")

    # the model keeps asking for the tool even after it stops being offered
    model = FakeModel(
        calls(("flaky", '{"x": "1"}')),
        calls(("flaky", '{"x": "2"}')),
        calls(("flaky", '{"x": "3"}')),
        text("giving up"),
    )
    loop = AgentLoop(model=model, tools=[flaky], max_turns=10, max_tool_failures=2)
    result = await loop.arun("go")

    assert executions == ["1", "2"], "the tool must stop being executed at its budget"
    assert result.status == "completed"
    assert result.final_output == "giving up"
    # once disabled it is withdrawn from the schema list too
    assert model.calls[-1]["tools"] is None
    disabled_result = [e for e in result.events if e.error == "tool disabled"]
    assert len(disabled_result) == 1


@pytest.mark.asyncio
async def test_max_turns_terminates():
    model = FakeModel(*[calls(("weather", '{"city": "X"}')) for _ in range(5)])
    loop = AgentLoop(model=model, tools=[weather], max_turns=3)
    result = await loop.arun("loop forever")

    assert result.status == "max_turns"
    assert "max_turns (3)" in result.error


@pytest.mark.asyncio
async def test_tool_exception_is_surfaced_not_raised():
    def bad(x: str) -> str:
        """Bad.

        Args:
            x: anything.
        """
        raise ValueError("nope")

    model = FakeModel(calls(("bad", '{"x": "1"}')), text("ok"))
    loop = AgentLoop(model=model, tools=[bad])
    result = await loop.arun("go")

    (event,) = [e for e in result.events if e.type == "tool_result" and e.error]
    assert event.error == "ValueError: nope"


@pytest.mark.asyncio
async def test_context_is_passed_to_context_param():
    seen = {}

    def needs_ctx(wrapper: "RunContextWrapper[object]", q: str) -> str:  # noqa: F821
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


@pytest.mark.asyncio
async def test_message_list_input_is_passed_through():
    model = FakeModel(text("ok"))
    loop = AgentLoop(model=model)
    await loop.arun(
        [{"role": "user", "content": "a"}, {"role": "assistant", "content": "b"}]
    )

    assert [m["content"] for m in model.calls[0]["messages"]] == ["a", "b"]


@pytest.mark.asyncio
async def test_astream_emits_expected_event_sequence():
    model = FakeModel(calls(("weather", '{"city": "Rome"}')), text("sunny"))
    loop = AgentLoop(model=model, tools=[weather])

    types = [e.type async for e in loop.astream("go")]
    assert types == [
        "run_start",
        "tool_call",
        "tool_result",
        "message",
        "run_end",
    ]


@pytest.mark.asyncio
async def test_astream_text_deltas():
    loop = AgentLoop(model=FakeModel(text("one two three")))
    deltas = [
        e.text
        async for e in loop.astream("go", stream_text=True)
        if e.type == "text_delta"
    ]
    assert "".join(deltas).strip() == "one two three"


@pytest.mark.asyncio
async def test_with_model_shares_tools():
    loop = AgentLoop(model=FakeModel(text("a")), tools=[weather])
    clone = loop.with_model(FakeModel(text("b")))

    assert clone.tools is loop.tools
    assert (await clone.arun("go")).final_output == "b"


def test_run_rejects_being_called_inside_event_loop():
    import asyncio

    async def main():
        with pytest.raises(RuntimeError, match="running event loop"):
            AgentLoop(model=FakeModel(text("x"))).run("go")

    asyncio.run(main())


# --------------------------------------------------- Agentor integration


def native(model, **kwargs):
    from agentor import Agentor

    return Agentor(name="T", model=model, engine="native", api_key="test", **kwargs)


def test_agentor_defaults_to_the_agents_engine():
    from agentor import Agentor

    agent = Agentor(name="T", model="gpt-4o-mini", api_key="test")
    assert agent.engine == "agents"
    assert agent.agent is not None


def test_agentor_native_run():
    result = native(FakeModel(text("hi there")), tools=[weather]).run("go")
    assert result.final_output == "hi there"


def test_agentor_native_exposes_tool_metadata_for_a2a():
    agent = native(FakeModel(text("x")), tools=[weather])
    # serve() builds A2A skills from name/description on each tool
    assert [(t.name, t.description) for t in agent.tools] == [("weather", "Weather.")]


@pytest.mark.asyncio
async def test_agentor_native_stream_chat_matches_wire_format():
    agent = native(
        FakeModel(calls(("weather", '{"city": "Rome"}')), text("sunny")),
        tools=[weather],
    )
    outputs = [o async for o in agent.stream_chat("go", serialize=False)]

    assert [o.tool_action.type for o in outputs if o.tool_action] == [
        "tool_called",
        "tool_output",
    ]
    assert outputs[-1].message == "sunny"
    assert all(o.type == "run_item_stream_event" for o in outputs)


@pytest.mark.asyncio
async def test_agentor_native_chat_non_streaming():
    agent = native(FakeModel(text("answer")))
    result = await agent.chat("go")
    assert result.final_output == "answer"


def test_agentor_native_rejects_mcp_servers_loudly():
    from agentor.mcp import MCPServerStreamableHttp

    server = MCPServerStreamableHttp(name="m", params={"url": "http://example"})
    with pytest.raises(NotImplementedError, match="MCP servers"):
        native(FakeModel(text("x")), tools=[server])


@pytest.mark.asyncio
async def test_agentor_native_falls_back_on_rate_limit():
    import httpx
    import openai

    response = httpx.Response(
        429, request=httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    )

    class Failing:
        model = "primary"

        async def complete(self, messages, tools=None):
            raise openai.RateLimitError("rate limited", response=response, body=None)

    agent = native(Failing())
    agent._loop.with_model = lambda *a, **k: AgentLoop(
        model=FakeModel(text("from fallback"))
    )

    result = await agent.arun("go", fallback_models=["backup"])
    assert result.final_output == "from fallback"
