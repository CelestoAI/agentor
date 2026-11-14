"""Offline execution tests for the optional Keenable MCP example."""

import json
from types import SimpleNamespace

import pytest
from examples import keenable_search

from agentor import Agentor
from tests.test_engine import FakeModel, calls, text
from tests.test_engine_mcp import FakeSession, remote_tool


@pytest.fixture
def example_connection(monkeypatch):
    monkeypatch.delenv("KEENABLE_API_KEY", raising=False)
    server = keenable_search.create_server()
    session = FakeSession(
        [remote_tool("search_web_pages"), remote_tool("fetch_page_content")],
        results={
            "search_web_pages": "Source: https://example.org/docs - durable agent runs",
            "fetch_page_content": "Agent runs are persisted and can be resumed.",
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
    monkeypatch.setattr(keenable_search, "create_server", lambda: server)
    return server, session, closed


@pytest.mark.asyncio
async def test_example_tools_reach_agent_and_results_reach_model(example_connection):
    server, session, closed = example_connection
    model = FakeModel(
        calls(
            (
                "keenable_search_web_pages",
                json.dumps({"query": "durable agent runs"}),
            )
        ),
        calls(("keenable_fetch_page_content", '{"url": "https://example.org/docs"}')),
        text("Runs can be resumed. Source: https://example.org/docs"),
    )
    agent = Agentor(name="Researcher", model=model, tools=[server])
    result = await agent.arun("How do durable runs work?")

    assert "https://example.org/docs" in result.final_output
    assert [name for name, _ in session.calls] == [
        "search_web_pages",
        "fetch_page_content",
    ]
    assert {t["function"]["name"] for t in model.calls[0]["tools"]} == {
        "keenable_search_web_pages",
        "keenable_fetch_page_content",
    }
    tool_messages = [m for m in model.calls[-1]["messages"] if m["role"] == "tool"]
    assert [m["content"] for m in tool_messages] == [
        session._results["search_web_pages"],
        session._results["fetch_page_content"],
    ]
    assert closed == [True]


@pytest.mark.asyncio
async def test_tools_only_reuses_session_and_closes_on_tool_error(
    example_connection, capsys
):
    _server, session, closed = example_connection
    await keenable_search.search_without_model(
        "agent durable runs", "https://example.org/docs"
    )
    assert "persisted" in capsys.readouterr().out
    search_args, fetch_args = [args for _, args in session.calls]
    assert search_args["session_id"] == fetch_args["session_id"]
    assert fetch_args["url"] == "https://example.org/docs"
    assert closed == [True]

    async def fail(name, arguments):
        return SimpleNamespace(
            content=[SimpleNamespace(text="Rate limit reached")], is_error=True
        )

    session.call_tool = fail
    with pytest.raises(RuntimeError, match="Rate limit reached"):
        await keenable_search.search_without_model("agent durable runs")
    assert closed == [True, True]


def test_endpoint_and_key_selection(monkeypatch):
    monkeypatch.delenv("KEENABLE_API_KEY", raising=False)
    server = keenable_search.create_server()
    assert server.url == keenable_search.PUBLIC_URL
    assert "X-API-Key" not in server.headers

    monkeypatch.setenv("KEENABLE_API_KEY", "test-key")
    server = keenable_search.create_server()
    assert server.url == keenable_search.KEYED_URL
    assert server.headers["X-API-Key"] == "test-key"
