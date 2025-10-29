from agentor.mcp.server import LiteMCP

# Create the ASGI app
app = LiteMCP(
    name="my-mcp-server",
    version="1.0.0",
    instructions="A simple MCP server example",
)


# Register a simple tool
@app.tool(description="Get weather for a location")
def get_weather(location: str) -> str:
    """Get current weather for a location"""
    return f"🌤️ Weather in {location}: Sunny, 72°F"


# Register a prompt
@app.prompt(description="Generate a greeting")
def greeting(name: str, style: str = "formal") -> str:
    """Generate a personalized greeting"""
    if style == "formal":
        return f"Good day, {name}. How may I assist you today?"
    else:
        return f"Hey {name}! What's up?"


# Register a resource
@app.resource(uri="config://settings", name="Settings", mime_type="application/json")
def get_settings(uri: str) -> str:
    """Get application settings"""
    return '{"theme": "dark", "language": "en"}'


if __name__ == "__main__":
    # Method 1: Direct run (simplest)
    app.run()

    # Method 2: Run with custom uvicorn settings
    # app.run(reload=True, log_level="debug")

    # Method 3: Use with uvicorn CLI
    # $ uvicorn lite_mcp_example:app --host 0.0.0.0 --port 8000 --reload

    # Method 4: Programmatic uvicorn
    # import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
