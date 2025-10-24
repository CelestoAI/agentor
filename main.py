from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from mcp.types import Icon
from src.agentor.mcp_api_router import MCPAPIRouter
import uvicorn

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create MCP router with configuration
mcp_router = MCPAPIRouter(
    prefix="/mcp",
    name="celesto-mcp",
    version="0.1.0",
    instructions="This is a test MCP server.",
    website_url="https://celesto.ai",
    icons=[
        Icon(
            src="https://celesto.ai/favicon.ico",
            mimeType="image/x-icon",
        )
    ],
)


@mcp_router.method("tools/list")
async def custom_tools_list(body: dict):
    """Custom tools list with actual tools"""
    return {
        "tools": [
            {
                "name": "get_weather",
                "description": "Get weather for a location",
                "inputSchema": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            }
        ]
    }


@mcp_router.method("tools/call")
async def call_tool(body: dict):
    """Handle tool calls"""
    params = body.get("params", {})
    tool_name = params.get("name")

    if tool_name == "get_weather":
        location = params.get("arguments", {}).get("location")
        return {
            "content": [
                {"type": "text", "text": f"The weather in {location} is sunny!"}
            ]
        }

    return {"error": "Unknown tool"}


app.include_router(mcp_router.get_fastapi_router())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
