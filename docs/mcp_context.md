# MCP Context: Accessing Headers and Cookies in Tools

The MCP Context feature allows tool functions to access HTTP request-level data such as headers and cookies. This is useful for implementing authentication, session management, user preferences, and other request-specific behaviors.

## Overview

The `Context` class provides a simple interface to access:
- **Headers**: All HTTP headers from the incoming request
- **Cookies**: All cookies from the incoming request

## Basic Usage

```python
from agentor.mcp import MCPAPIRouter, Context, get_context
from fastapi import Depends

mcp_router = MCPAPIRouter()

@mcp_router.tool(description="Get weather with user context")
def get_weather(location: str, ctx: Context = Depends(get_context)) -> str:
    """Get current weather information with user context"""
    # Access request headers
    user_agent = ctx.headers.get("user-agent", "unknown")
    auth_header = ctx.headers.get("authorization", "no-auth")
    
    # Access cookies
    session_id = ctx.cookies.get("session_id", "no-session")
    user_pref = ctx.cookies.get("weather_units", "fahrenheit")
    
    # Use context in your logic
    temp_symbol = "°F" if user_pref == "fahrenheit" else "°C"
    
    return f"Weather in {location}: Sunny, 72{temp_symbol}"
```

## Using Annotated Type Syntax

You can also use Python's `Annotated` type syntax:

```python
from typing import Annotated
from agentor.mcp import MCPAPIRouter, Context, get_context
from fastapi import Depends

mcp_router = MCPAPIRouter()

@mcp_router.tool()
def check_auth(
    resource: str, 
    ctx: Annotated[Context, Depends(get_context)]
) -> str:
    """Check authorization for a resource"""
    auth_header = ctx.headers.get("authorization", "no-auth")
    return f"Accessing {resource} with {auth_header}"
```

## Context Fields

### Headers
- Type: `Dict[str, str]`
- Contains all HTTP headers from the request
- Header names are lowercase (e.g., `"user-agent"`, `"authorization"`)
- Use `.get()` method for safe access with defaults

### Cookies
- Type: `Dict[str, str]`
- Contains all cookies from the request
- Use `.get()` method for safe access with defaults

## Common Use Cases

### 1. Authentication
```python
@mcp_router.tool()
def secure_action(action: str, ctx: Context = Depends(get_context)) -> str:
    auth_token = ctx.headers.get("authorization", "")
    if not auth_token.startswith("Bearer "):
        return "Error: Unauthorized"
    # Process authenticated action
    return f"Action {action} completed"
```

### 2. User Preferences
```python
@mcp_router.tool()
def get_content(page: str, ctx: Context = Depends(get_context)) -> str:
    language = ctx.headers.get("accept-language", "en")
    theme = ctx.cookies.get("theme", "light")
    return f"Content for {page} in {language} with {theme} theme"
```

### 3. Session Management
```python
@mcp_router.tool()
def add_to_cart(item: str, ctx: Context = Depends(get_context)) -> str:
    session_id = ctx.cookies.get("session_id")
    if not session_id:
        return "Error: No session"
    # Add item to user's cart
    return f"Added {item} to cart (session: {session_id})"
```

### 4. Analytics and Logging
```python
@mcp_router.tool()
def search(query: str, ctx: Context = Depends(get_context)) -> str:
    user_agent = ctx.headers.get("user-agent", "unknown")
    referer = ctx.headers.get("referer", "direct")
    # Log search with context
    logger.info(f"Search: {query} from {user_agent} via {referer}")
    return f"Results for {query}"
```

## Important Notes

1. **Schema Generation**: Context parameters are automatically excluded from the tool's input schema, as they are resolved via dependency injection.

2. **Optional Context**: Tools can work with or without context. Only include the `ctx` parameter if your tool needs request data.

3. **Thread Safety**: The context uses Python's `contextvars` which are thread-safe and work correctly in async environments.

4. **Empty Context**: If a tool is called outside of a request context (e.g., during testing), `get_context()` returns a Context with empty headers and cookies dictionaries.

## Complete Example

See `examples/mcp_context_example.py` for a complete working example that demonstrates:
- Accessing headers and cookies
- Using context in tool logic
- Tools with and without context
- Running the server

## Testing

To test tools that use context, use FastAPI's TestClient:

```python
from fastapi.testclient import TestClient
from fastapi import FastAPI

app = FastAPI()
app.include_router(mcp_router.get_fastapi_router())
client = TestClient(app)

response = client.post(
    "/mcp",
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_weather",
            "arguments": {"location": "NYC"}
        }
    },
    headers={"user-agent": "test-client/1.0"},
    cookies={"session_id": "test-123"}
)
```

See `tests/test_mcp_context.py` for comprehensive test examples.
