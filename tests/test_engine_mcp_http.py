"""MCP SDK 2 compatibility over HTTP, with real discovery and tool calls.

Failure modes recorded before implementation: transport/pagination API changes,
schema and result field aliases, lost structured-only content, remote errors,
credential forwarding and leaked clients after failed discovery or close.
The client-factory hook also serves Celesto's outbound endpoint guards.
"""

import asyncio
import json

import httpx2
import pytest
from mcp import MCPError
from mcp.server import Server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from agentor.engine.mcp import MCPServer


@pytest.mark.asyncio
async def test_mcp_client_discovers_pages_calls_tools_and_closes_http(tmp_path):
    calls = []
    exchanges = []
    clients = []
    fail_discovery = False
    next_cursors = {None: "page2", "page2": None}

    async def list_tools(ctx, params):
        if fail_discovery:
            raise RuntimeError("discovery unavailable")
        cursor = params.cursor if params else None
        names = ["echo"] if cursor is None else ["structured", "fail"]
        return ListToolsResult(
            tools=[
                Tool(
                    name=name,
                    description="HTTP fixture tool",
                    input_schema={
                        "type": "object",
                        "properties": {"value": {"type": "string"}},
                        "required": ["value"],
                    },
                )
                for name in names
            ],
            next_cursor=next_cursors[cursor],
        )

    async def call_tool(ctx, params):
        calls.append({"name": params.name, "arguments": params.arguments})
        if params.name == "structured":
            return CallToolResult(content=[], structured_content=params.arguments)
        return CallToolResult(
            content=[TextContent(type="text", text=params.arguments["value"])],
            is_error=params.name == "fail",
        )

    app = Server(
        "Fixture", on_list_tools=list_tools, on_call_tool=call_tool
    ).streamable_http_app(json_response=True, stateless_http=True)

    async def record(response):
        await response.aread()
        exchanges.append(
            {
                "method": response.request.method,
                "path": response.request.url.path,
                "authorization": response.request.headers.get("authorization"),
                "status": response.status_code,
                "body": response.json()
                if response.content
                and "application/json" in response.headers.get("content-type", "")
                else response.text,
            }
        )

    def http_client(**kwargs):
        client = httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app),
            event_hooks={"response": [record]},
            **kwargs,
        )
        clients.append(client)
        return client

    remote = MCPServer(
        "http://localhost:8000/mcp",
        headers={"Authorization": "Bearer synthetic"},
        tool_prefix="remote__",
        http_client_factory=http_client,
    )
    async with app.router.lifespan_context(app):
        tools = await remote.connect()
        assert [tool.name for tool in tools] == [
            "remote__echo",
            "remote__structured",
            "remote__fail",
        ]
        assert tools[0].parameters["required"] == ["value"]
        with pytest.raises(RuntimeError, match="already connected"):
            await remote.connect()
        assert await tools[0].call({"value": "hello"}) == "hello"
        assert await tools[1].call({"value": "structured"}) == "{'value': 'structured'}"
        with pytest.raises(RuntimeError, match="remote refused"):
            await tools[2].call({"value": "remote refused"})
        await remote.close()
        assert clients[0].is_closed
        assert remote._session is None
        fail_discovery = True
        with pytest.raises(MCPError, match="discovery unavailable"):
            await remote.connect()
        assert clients[1].is_closed
        assert remote._session is None
        assert remote._stack is None

        fail_discovery = False
        for next_cursors in (
            {None: "page2", "page2": "page2"},
            {None: "page2", "page2": "page3", "page3": "page2"},
        ):
            with pytest.raises(RuntimeError, match="pagination cursor"):
                await asyncio.wait_for(remote.connect(), timeout=5)
            assert clients[-1].is_closed
            assert remote._session is None
            assert remote._stack is None

    (tmp_path / "agentor-sdk2-http.json").write_text(
        json.dumps({"calls": calls, "http_exchanges": exchanges}, indent=2)
    )
    assert calls == [
        {"name": "echo", "arguments": {"value": "hello"}},
        {"name": "structured", "arguments": {"value": "structured"}},
        {"name": "fail", "arguments": {"value": "remote refused"}},
    ]
    assert all(
        exchange["authorization"] == "Bearer synthetic" for exchange in exchanges
    )
