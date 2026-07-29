"""Tests for the native engine's MCP client (agentor.engine.mcp)."""

import asyncio
from types import SimpleNamespace

import pytest

from agentor.engine import AgentLoop
from agentor.engine.mcp import MCPServer, _content_to_text
from tests.test_engine import FakeModel, calls, text, weather


def remote_tool(name, description="", schema=None):
    return SimpleNamespace(
        name=name,
        description=description,
        inputSchema=schema or {"type": "object", "properties": {}},
    )


class FakeSession:
    """Stands in for an mcp ClientSession."""

    def __init__(self, tools, results=None, is_error=False):
        self._tools = tools
        self._results = results or {}
        self._is_error = is_error
        self.calls = []

    async def list_tools(self):
        return SimpleNamespace(tools=self._tools)

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return SimpleNamespace(
            content=[SimpleNamespace(text=self._results.get(name, "ok"))],
            structuredContent=None,
            isError=self._is_error,
        )


def connected(session) -> MCPServer:
    server = MCPServer("http://example/mcp", name="fake")
    server._session = session
    server._stack = None
    return server


# ------------------------------------------------------------ content


def test_content_to_text_joins_text_parts():
    result = SimpleNamespace(
        content=[SimpleNamespace(text="a"), SimpleNamespace(text="b")],
        structuredContent=None,
    )
    assert _content_to_text(result) == "a\nb"


def test_content_to_text_falls_back_to_structured_content():
    result = SimpleNamespace(content=[], structuredContent={"k": 1})
    assert _content_to_text(result) == "{'k': 1}"


def test_content_to_text_keeps_non_text_content():
    """Images and resources must reach the model as something, not vanish."""
    blob = SimpleNamespace(text=None, model_dump=lambda: {"type": "image"})
    result = SimpleNamespace(content=[blob], structuredContent=None)
    assert "image" in _content_to_text(result)


# ------------------------------------------------------------ discovery


@pytest.mark.asyncio
async def test_list_tools_maps_remote_schema():
    schema = {"type": "object", "properties": {"q": {"type": "string"}}}
    server = connected(FakeSession([remote_tool("search", "Search things", schema)]))

    (tool,) = await server.list_tools()
    assert tool.name == "search"
    assert tool.description == "Search things"
    assert tool.parameters == schema
    assert tool.to_openai()["function"]["name"] == "search"


@pytest.mark.asyncio
async def test_tool_prefix_disambiguates_servers():
    server = MCPServer("http://example/mcp", tool_prefix="a_")
    server._session = FakeSession([remote_tool("search")])

    (tool,) = await server.list_tools()
    assert tool.name == "a_search"


@pytest.mark.asyncio
async def test_list_tools_requires_connection():
    with pytest.raises(RuntimeError, match="not connected"):
        await MCPServer("http://example/mcp").list_tools()


@pytest.mark.asyncio
async def test_calling_a_remote_tool_forwards_arguments():
    session = FakeSession([remote_tool("search")], results={"search": "found it"})
    server = connected(session)

    (tool,) = await server.list_tools()
    assert await tool.call({"q": "cats"}) == "found it"
    assert session.calls == [("search", {"q": "cats"})]


@pytest.mark.asyncio
async def test_remote_error_raises_so_the_failure_budget_applies():
    session = FakeSession(
        [remote_tool("bad")], results={"bad": "upstream down"}, is_error=True
    )
    server = connected(session)

    (tool,) = await server.list_tools()
    with pytest.raises(RuntimeError, match="upstream down"):
        await tool.call({})


# ------------------------------------------------------------ loop wiring


@pytest.mark.asyncio
async def test_remote_tools_are_available_during_a_run_and_removed_after():
    session = FakeSession(
        [remote_tool("remote_search")], results={"remote_search": "hit"}
    )

    class Server(MCPServer):
        closed = False

        async def connect(self):
            self._session = session
            return await self.list_tools()

        async def close(self):
            Server.closed = True

    model = FakeModel(calls(("remote_search", '{"q": "x"}')), text("done"))
    loop = AgentLoop(
        model=model,
        tools=[weather],
        mcp_servers=[Server("http://example/mcp")],
    )
    result = await loop.arun("go")

    assert result.final_output == "done"
    assert [e.result for e in result.events if e.type == "tool_result"] == ["hit"]
    # offered to the model during the run...
    assert {t["function"]["name"] for t in model.calls[0]["tools"]} == {
        "weather",
        "remote_search",
    }
    # ...and gone afterwards, so the loop is reusable
    assert sorted(loop.tools) == ["weather"]
    assert Server.closed


@pytest.mark.asyncio
async def test_remote_tool_does_not_shadow_a_local_one():
    session = FakeSession([remote_tool("weather")], results={"weather": "REMOTE"})

    class Server(MCPServer):
        async def connect(self):
            self._session = session
            return await self.list_tools()

        async def close(self):
            pass

    model = FakeModel(calls(("weather", '{"city": "A"}')), text("done"))
    loop = AgentLoop(
        model=model, tools=[weather], mcp_servers=[Server("http://example/mcp")]
    )
    result = await loop.arun("go")

    (event,) = [e for e in result.events if e.type == "tool_result"]
    assert event.result == "A: sunny", "the local tool must win"


@pytest.mark.asyncio
async def test_servers_are_closed_even_when_a_run_fails():
    class Server(MCPServer):
        closed = False

        async def connect(self):
            self._session = FakeSession([remote_tool("x")])
            return await self.list_tools()

        async def close(self):
            Server.closed = True

    class Exploding:
        model = "boom"

        async def complete(self, messages, tools=None):
            raise RuntimeError("model exploded")

    loop = AgentLoop(model=Exploding(), mcp_servers=[Server("http://example/mcp")])
    with pytest.raises(RuntimeError, match="model exploded"):
        await loop.arun("go")

    assert Server.closed, "a failed run must not leak connections"


def test_closing_from_a_different_event_loop_explains_itself():
    """anyio's own error names cancel scopes, not the actual mistake."""
    server = MCPServer("http://example/mcp", name="fake")

    async def connect():
        server._loop = asyncio.get_running_loop()
        server._stack = object()

    asyncio.run(connect())

    async def close():
        await server.close()

    with pytest.raises(RuntimeError, match="different event loop"):
        asyncio.run(close())
