"""MCP client for the native engine.

Built on the official `mcp` package rather than an agent framework's wrapper,
so remote tools become ordinary `Tool` objects and the rest of the engine does
not need to know where a tool came from.
"""

from __future__ import annotations

import logging
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional

from agentor.engine.tools import Tool

logger = logging.getLogger(__name__)


def _content_to_text(result: Any) -> str:
    """Flatten an MCP CallToolResult into the string a tool returns."""
    parts: List[str] = []
    for item in getattr(result, "content", None) or []:
        text = getattr(item, "text", None)
        if text is not None:
            parts.append(text)
            continue
        # non-text content (images, resources) still needs to reach the model
        # as something; its own repr is better than dropping it silently
        parts.append(str(getattr(item, "model_dump", lambda: item)()))

    if not parts and getattr(result, "structuredContent", None) is not None:
        return str(result.structuredContent)
    return "\n".join(parts)


class MCPServer:
    """A streamable-HTTP MCP server whose tools an agent can call.

    Usable directly as an async context manager, or handed to `AgentLoop`,
    which connects it for the duration of a run.
    """

    def __init__(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
        name: Optional[str] = None,
        tool_prefix: Optional[str] = None,
    ):
        self.url = url
        self.headers = headers
        self.timeout = timeout
        self.name = name or url
        #: guards against two servers exposing the same tool name
        self.tool_prefix = tool_prefix
        self._stack: Optional[AsyncExitStack] = None
        self._session: Any = None
        self._loop: Any = None

    async def connect(self) -> List[Tool]:
        import asyncio

        from mcp import ClientSession
        from mcp.client.streamable_http import streamablehttp_client

        self._loop = asyncio.get_running_loop()
        stack = AsyncExitStack()
        try:
            read, write, _ = await stack.enter_async_context(
                streamablehttp_client(
                    self.url, headers=self.headers, timeout=self.timeout
                )
            )
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self._stack = stack
            self._session = session
            # Discovery stays inside the guard: if it raises after the session
            # opens, connect() never returns, so nothing else can close it.
            return await self.list_tools()
        except BaseException:
            self._stack = None
            self._session = None
            self._loop = None
            await stack.aclose()
            raise

    async def list_tools(self) -> List[Tool]:
        if self._session is None:
            raise RuntimeError(f"MCP server {self.name!r} is not connected.")

        listed = await self._session.list_tools()
        tools: List[Tool] = []
        for remote in listed.tools:
            name = (
                f"{self.tool_prefix}{remote.name}" if self.tool_prefix else remote.name
            )
            tools.append(
                Tool(
                    name=name,
                    description=remote.description or "",
                    parameters=remote.inputSchema
                    or {"type": "object", "properties": {}},
                    invoke=self._invoker(remote.name),
                )
            )
        return tools

    def _invoker(self, remote_name: str):
        async def invoke(**kwargs: Any) -> str:
            result = await self._session.call_tool(remote_name, kwargs)
            text = _content_to_text(result)
            if getattr(result, "isError", False):
                # raise so the loop's failure budget applies to remote tools too
                raise RuntimeError(text or "MCP tool reported an error")
            return text

        return invoke

    async def close(self) -> None:
        if self._stack is None:
            return

        import asyncio

        if self._loop is not None and self._loop is not asyncio.get_running_loop():
            # anyio binds the session's cancel scope to the task that opened it.
            # Closing from elsewhere raises "Attempted to exit cancel scope in a
            # different task", which says nothing about the actual mistake.
            self._stack = None
            self._session = None
            raise RuntimeError(
                f"MCP server {self.name!r} was connected on a different event "
                "loop than the one closing it. Connect and close within the "
                "same asyncio.run(), or use `async with MCPServer(...)`."
            )

        try:
            await self._stack.aclose()
        except Exception as e:
            logger.warning("Error closing MCP server %s: %s", self.name, e)
        finally:
            self._stack = None
            self._session = None
            self._loop = None

    async def __aenter__(self) -> "MCPServer":
        await self.connect()
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()
