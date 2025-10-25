# LiteMCP - ASGI-Compatible MCP Server

`LiteMCP` is a lightweight, ASGI-compatible MCP (Model Context Protocol) server built on top of FastAPI. It provides a simple, decorator-based API for creating MCP servers that can be deployed with any ASGI server.

## Features

- ✅ **ASGI Compatible**: Works with uvicorn, hypercorn, daphne, and other ASGI servers
- ✅ **FastAPI-like Decorators**: Familiar `@app.tool()`, `@app.prompt()`, `@app.resource()` syntax
- ✅ **Built-in CORS**: Optional CORS middleware for web-based clients
- ✅ **Type Safety**: Full type hints and automatic schema generation
- ✅ **Logging**: Proper logging with configurable levels

## Quick Start

```python
from agentor.mcp import LiteMCP

# Create the app
app = LiteMCP(name="my-server", version="1.0.0", instructions="My MCP server")


# Register a tool
@app.tool(description="Get weather")
def get_weather(location: str) -> str:
    return f"Weather in {location}: Sunny"


# Run the server
if __name__ == "__main__":
    app.run()
```

## Usage Methods

### 1. Direct Run (Simplest)

```python
app = LiteMCP()
app.run()
```

### 2. Custom Uvicorn Settings

```python
app = LiteMCP()
app.run(reload=True, log_level="debug", workers=4)
```

### 3. Uvicorn CLI

```bash
# Save your app in server.py
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Programmatic Uvicorn

```python
import uvicorn

app = LiteMCP()
uvicorn.run(app, host="0.0.0.0", port=8000)
```

### 5. Run with Gunicorn

```bash
# Gunicorn with uvicorn workers
gunicorn server:app --workers 4 --worker-class uvicorn.workers.UvicornWorker
```

## Configuration

### Constructor Parameters

```python
LiteMCP(
    host="0.0.0.0",  # Host to bind (for run() method)
    port=8000,  # Port to bind (for run() method)
    enable_cors=True,  # Enable CORS middleware
    name="mcp-server",  # Server name
    version="1.0.0",  # Server version
    instructions="...",  # Server instructions
    website_url="...",  # Website URL
    icons=[...],  # Server icons
    prefix="/mcp",  # MCP endpoint prefix
)
```

## Decorators

### @app.tool()

Register a tool that can be called by MCP clients:

```python
@app.tool(
    name="custom_name",  # Optional: defaults to function name
    description="Tool description",
    input_schema={...},  # Optional: auto-generated from function signature
)
def my_tool(param1: str, param2: int = 10) -> str:
    return f"Result: {param1} {param2}"
```

### @app.prompt()

Register a prompt template:

```python
@app.prompt(
    name="custom_name",  # Optional: defaults to function name
    description="Prompt description",
    arguments=[...],  # Optional: auto-generated from function signature
)
def my_prompt(context: str, style: str = "formal") -> str:
    return f"Generate a {style} response about {context}"
```

### @app.resource()

Register a resource that can be read by MCP clients:

```python
@app.resource(
    uri="resource://path",
    name="Resource Name",
    description="Resource description",
    mime_type="text/plain",
)
def my_resource(uri: str) -> str:
    return "Resource content"
```

### @app.method()

Register a custom JSON-RPC method handler:

```python
@app.method("custom/method")
async def custom_handler(body: dict):
    # Handle custom method
    return {"result": "success"}
```

## Production Deployment

### With Gunicorn + Uvicorn Workers

```bash
gunicorn server:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --access-logfile - \
    --error-logfile -
```

## Testing

Since `LiteMCP` is an ASGI app, you can test it with FastAPI's test client:

```python
from fastapi.testclient import TestClient

app = LiteMCP()


@app.tool()
def test_tool(x: int) -> int:
    return x * 2


client = TestClient(app.app)
response = client.post(
    "/mcp",
    json={
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "test_tool", "arguments": {"x": 5}},
    },
)
assert response.status_code == 200
```

## Comparison with FastMCP

### Key Architectural Difference

**LiteMCP** is a native ASGI application that integrates directly with your existing FastAPI/Starlette app using standard routing patterns. You can use it standalone or include it in your app naturally.

**FastMCP** requires mounting as a sub-application, which means you diverge from standard FastAPI primitives when serving MCP tools alongside your regular backend:

```python
# FastMCP - Requires mounting as sub-app
from starlette.applications import Starlette
from starlette.routing import Mount
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("My App")
app = Starlette(
    routes=[
        Mount("/mcp", app=mcp.streamable_http_app())  # Separate ASGI app
    ]
)

# LiteMCP - Native ASGI integration
from agentor.mcp import LiteMCP

app = LiteMCP(name="My App")  # IS the ASGI app
# or easily include in existing FastAPI:
# fastapi_app.include_router(app.get_fastapi_router())
```

### Feature Comparison

| Feature | LiteMCP | FastMCP |
|---------|---------|---------|
| ASGI Compatible | ✅ Yes | ✅ Yes |
| Integration Pattern | Native ASGI app | Requires mounting |
| FastAPI Primitives | ✅ Standard patterns | ⚠️ Diverges (sub-app) |
| Decorator API | ✅ Yes | ✅ Yes |
| Custom Methods | ✅ Full support | ⚠️ Limited |
| CORS Support | ✅ Built-in | ❌ Manual setup |
| Lightweight | ✅ Minimal deps | ⚠️ More deps |
| Use with Existing Backend | ✅ Easy | ⚠️ Requires mounting |

### When to Use Each

**Use LiteMCP when:**

- You want to serve MCP tools alongside your existing FastAPI/Starlette backend
- You prefer standard FastAPI patterns and routing
- You want full control over custom JSON-RPC methods
- You want minimal dependencies

**Use FastMCP when:**

- You're building a standalone MCP server
- You want the official SDK implementation
- You don't need to integrate with existing web services

## Examples

See `docs/examples/lite_mcp_example.py` for a complete working example.

## License

Apache 2.0
