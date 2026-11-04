"""Failure boundaries for the optional local lookup example."""

import pytest
from examples import sem_lookup


@pytest.mark.asyncio
async def test_missing_token_does_not_connect(monkeypatch):
    monkeypatch.delenv("SEM_MCP_HTTP_TOKEN", raising=False)

    def unexpected_connection(**kwargs):
        pytest.fail("No connection should be created without the token")

    monkeypatch.setattr(sem_lookup, "MCPServer", unexpected_connection)
    with pytest.raises(ValueError, match="SEM_MCP_HTTP_TOKEN"):
        await sem_lookup.lookup("parse_config")


@pytest.mark.asyncio
async def test_missing_tool_closes_connection(monkeypatch):
    monkeypatch.setenv("SEM_MCP_HTTP_TOKEN", "test-only-token-" * 3)
    closed = []

    class Server:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            closed.append(True)

        async def list_tools(self):
            return []

    monkeypatch.setattr(sem_lookup, "MCPServer", Server)
    with pytest.raises(RuntimeError, match="sem_find"):
        await sem_lookup.lookup("parse_config")
    assert closed == [True]
