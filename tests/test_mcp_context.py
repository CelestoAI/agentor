from agentor.mcp import MCPAPIRouter, Context, get_context
from fastapi import Depends
from fastapi.testclient import TestClient
import pytest
from typing import Annotated


@pytest.mark.asyncio
async def test_mcp_tool_with_context():
    """Test that tools can access request context (headers and cookies)"""
    router = MCPAPIRouter()

    @router.tool()
    def get_user_info(location: str, ctx: Context = Depends(get_context)) -> str:
        """Get user info with location"""
        user_agent = ctx.headers.get("user-agent", "unknown")
        session_id = ctx.cookies.get("session_id", "no-session")
        return f"{location}|{user_agent}|{session_id}"

    # Create a test client
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router.get_fastapi_router())
    client = TestClient(app)

    # Make a request with headers and cookies
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "get_user_info",
                "arguments": {"location": "NYC"}
            }
        },
        headers={"user-agent": "test-client/1.0"},
        cookies={"session_id": "test-session-123"}
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert result["result"]["content"][0]["text"] == "NYC|test-client/1.0|test-session-123"


@pytest.mark.asyncio
async def test_mcp_tool_with_annotated_context():
    """Test that tools can use Annotated syntax for context"""
    router = MCPAPIRouter()

    @router.tool()
    def check_auth(
        resource: str, 
        ctx: Annotated[Context, Depends(get_context)]
    ) -> str:
        """Check auth with resource"""
        auth_header = ctx.headers.get("authorization", "no-auth")
        return f"Accessing {resource} with {auth_header}"

    # Create a test client
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router.get_fastapi_router())
    client = TestClient(app)

    # Make a request with authorization header
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "check_auth",
                "arguments": {"resource": "documents"}
            }
        },
        headers={"authorization": "Bearer token123"}
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert result["result"]["content"][0]["text"] == "Accessing documents with Bearer token123"


@pytest.mark.asyncio
async def test_mcp_tool_without_context():
    """Test that tools work normally without context"""
    router = MCPAPIRouter()

    @router.tool()
    def simple_tool(message: str) -> str:
        """Simple tool without context"""
        return f"Echo: {message}"

    # Create a test client
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router.get_fastapi_router())
    client = TestClient(app)

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "simple_tool",
                "arguments": {"message": "hello"}
            }
        }
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    assert result["result"]["content"][0]["text"] == "Echo: hello"


@pytest.mark.asyncio
async def test_context_not_in_tool_schema():
    """Test that Context parameters are excluded from tool schema"""
    router = MCPAPIRouter()

    @router.tool()
    def tool_with_context(
        name: str,
        age: int,
        ctx: Context = Depends(get_context)
    ) -> str:
        """Tool with context"""
        return f"{name} is {age}"

    # Get the tool schema
    tool_meta = router.tools["tool_with_context"]
    schema = tool_meta.input_schema

    # Context should not be in the schema
    assert "name" in schema["properties"]
    assert "age" in schema["properties"]
    assert "ctx" not in schema["properties"]
    assert "name" in schema["required"]
    assert "age" in schema["required"]
    assert "ctx" not in schema.get("required", [])


@pytest.mark.asyncio
async def test_context_with_empty_headers_and_cookies():
    """Test that context works with empty headers and cookies"""
    router = MCPAPIRouter()

    @router.tool()
    def tool_with_context(
        message: str,
        ctx: Context = Depends(get_context)
    ) -> str:
        """Tool with context"""
        header_count = len(ctx.headers)
        cookie_count = len(ctx.cookies)
        return f"{message}|headers:{header_count}|cookies:{cookie_count}"

    # Create a test client
    from fastapi import FastAPI
    app = FastAPI()
    app.include_router(router.get_fastapi_router())
    client = TestClient(app)

    # Make a request without custom headers or cookies
    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "tool_with_context",
                "arguments": {"message": "test"}
            }
        }
    )

    assert response.status_code == 200
    result = response.json()
    assert "result" in result
    # Should have some default headers from the test client
    text = result["result"]["content"][0]["text"]
    assert text.startswith("test|headers:")
    assert "cookies:0" in text  # No cookies set
