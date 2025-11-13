from fastapi import FastAPI
from agentor.mcp import MCPAPIRouter

mcp_router = MCPAPIRouter()


# Register a tool
@mcp_router.tool(
    description="Get current weather for a location",
)
def get_weather(location: str) -> str:
    """Get current weather information
    
    Note: You can access request headers and cookies by adding a Context parameter:
    
    from agentor.mcp import Context, get_context
    from fastapi import Depends
    
    def get_weather(location: str, ctx: Context = Depends(get_context)) -> str:
        user_agent = ctx.headers.get("user-agent")
        session_id = ctx.cookies.get("session_id")
        ...
    
    See examples/mcp_context_example.py for full example.
    """
    return f"The weather in {location} is sunny with a temperature of 72°F!"


# Register a prompt
@mcp_router.prompt(description="Generate a code review prompt")
def code_review(language: str, code: str) -> list:
    """Generate a code review prompt"""
    return [
        {
            "role": "user",
            "content": {
                "type": "text",
                "text": f"Please review this {language} code:\n\n```{language}\n{code}\n```",
            },
        }
    ]


if __name__ == "__main__":
    import uvicorn

    app = FastAPI()
    app.include_router(mcp_router.get_fastapi_router())
    uvicorn.run(app, host="0.0.0.0", port=8000)
