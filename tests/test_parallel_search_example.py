"""Offline execution tests for the optional Parallel MCP example."""

import json
from types import SimpleNamespace

import pytest
from examples import parallel_search

from agentor import Agentor
from tests.test_engine import FakeModel, calls, text
from tests.test_engine_mcp import FakeSession, remote_tool


@pytest.fixture
def example_connection(monkeypatch):
    server = parallel_search.create_server()
    session = FakeSession(
        [remote_tool("web_search"), remote_tool("web_fetch")],
        results={
            "web_search": "Source: https://example.org/docs - durable agent runs",
            "web_fetch": "Agent runs are persisted and can be resumed.",
        },
    )
    closed = []

    async def connect():
        server._session = session
        return await server.list_tools()

    async def close():
        closed.append(True)
        server._session = None

    monkeypatch.setattr(server, "connect", connect)
    monkeypatch.setattr(server, "close", close)
    monkeypatch.setattr(parallel_search, "create_server", lambda: server)
    return server, session, closed


@pytest.mark.asyncio
async def test_example_tools_reach_agent_and_results_reach_model(example_connection):
    server, session, closed = example_connection
    model = FakeModel(
        calls(
            (
                "parallel_web_search",
                json.dumps(
                    {"objective": "Durable runs", "search_queries": ["agent runs"]}
                ),
            )
        ),
        calls(("parallel_web_fetch", '{"urls": ["https://example.org/docs"]}')),
        text("Runs can be resumed. Source: https://example.org/docs"),
    )
    agent = Agentor(name="Researcher", model=model, tools=[server])
    result = await agent.arun("How do durable runs work?")

    assert "https://example.org/docs" in result.final_output
    assert [name for name, _ in session.calls] == ["web_search", "web_fetch"]
    assert {t["function"]["name"] for t in model.calls[0]["tools"]} == {
        "parallel_web_search",
        "parallel_web_fetch",
    }
    tool_messages = [m for m in model.calls[-1]["messages"] if m["role"] == "tool"]
    assert [m["content"] for m in tool_messages] == [
        session._results["web_search"],
        session._results["web_fetch"],
    ]
    assert closed == [True]


@pytest.mark.asyncio
async def test_tools_only_reuses_session_and_closes_on_tool_error(
    example_connection, capsys
):
    _server, session, closed = example_connection
    await parallel_search.search_without_model(
        "agent durable runs", "https://example.org/docs"
    )
    assert "persisted" in capsys.readouterr().out
    search_args, fetch_args = [args for _, args in session.calls]
    assert search_args["session_id"] == fetch_args["session_id"]
    assert fetch_args["urls"] == ["https://example.org/docs"]
    assert closed == [True]

    async def fail(name, arguments):
        return SimpleNamespace(
            content=[SimpleNamespace(text="Rate limit reached")], is_error=True
        )

    session.call_tool = fail
    with pytest.raises(RuntimeError, match="Rate limit reached"):
        await parallel_search.search_without_model("agent durable runs")
    assert closed == [True, True]
