from agentor.mcp import MCPAPIRouter, Context, get_context
from fastapi import FastAPI, Depends

# Create MCP router
mcp_router = MCPAPIRouter()


@mcp_router.tool(description="Get weather with user context")
def get_weather(location: str, ctx: Context = Depends(get_context)) -> str:
    """Get current weather information with user context
    
    This example demonstrates how to access HTTP headers and cookies
    in your MCP tool functions.
    """
    # Access request headers
    user_agent = ctx.headers.get("user-agent", "unknown")
    auth_header = ctx.headers.get("authorization", "no-auth")
    
    # Access cookies
    session_id = ctx.cookies.get("session_id", "no-session")
    user_pref = ctx.cookies.get("weather_units", "fahrenheit")
    
    # Use context in your logic
    temp_symbol = "°F" if user_pref == "fahrenheit" else "°C"
    
    return (
        f"Weather in {location}: Sunny, 72{temp_symbol}\n"
        f"Session: {session_id}\n"
        f"User-Agent: {user_agent}\n"
        f"Auth: {auth_header}"
    )


@mcp_router.tool(description="Simple tool without context")
def get_time(timezone: str) -> str:
    """Get current time - no context needed
    
    Tools can work with or without context.
    Only include Context parameter if you need it.
    """
    return f"Current time in {timezone}: 12:00 PM"


if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(mcp_router.get_fastapi_router())
    
    print("MCP Server with Context Example")
    print("================================")
    print("Tools registered:")
    print("  - get_weather: Accesses headers and cookies via Context")
    print("  - get_time: Simple tool without context")
    print("\nStarting server on http://0.0.0.0:8000")
    print("\nExample request with headers and cookies:")
    print('curl -X POST http://localhost:8000/mcp \\')
    print('  -H "Content-Type: application/json" \\')
    print('  -H "Authorization: Bearer token123" \\')
    print('  -H "Cookie: session_id=user-abc; weather_units=celsius" \\')
    print('  -d \'{"jsonrpc":"2.0","id":1,"method":"tools/call",')
    print('       "params":{"name":"get_weather","arguments":{"location":"NYC"}}}\'')
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
