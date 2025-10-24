from fastapi import FastAPI, APIRouter, Request
from fastapi.middleware.cors import CORSMiddleware
from mcp.types import (
    Icon,
    Implementation,
    InitializeResult,
    ServerCapabilities,
    ToolsCapability,
    ResourcesCapability,
    PromptsCapability,
)
import uvicorn

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods including OPTIONS
    allow_headers=["*"],
)

router = APIRouter()

# Method registry
METHOD_HANDLERS = {}


def mcp_method(method_name: str):
    """Decorator to register MCP method handlers"""

    def decorator(func):
        METHOD_HANDLERS[method_name] = func
        return func

    return decorator


@mcp_method("initialize")
async def initialize(body: dict):
    params = body.get("params", {})
    request_id = body.get("id")

    result = InitializeResult(
        protocolVersion=params.get("protocolVersion"),
        capabilities=ServerCapabilities(
            tools=ToolsCapability(listChanged=True),
            resources=ResourcesCapability(listChanged=True),
            prompts=PromptsCapability(listChanged=True),
        ),
        serverInfo=Implementation(
            name="celesto-mcp",
            version="0.1.0",
            websiteUrl="https://celesto.ai",
            icons=[
                Icon(
                    src="https://celesto.ai/favicon.ico",
                    mimeType="image/x-icon",
                )
            ],
        ),
        instructions="This is a test MCP server.",
    )

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": result.model_dump(exclude_none=True),  # ← Changed this line
    }


@mcp_method("notifications/initialized")
async def initialized_notification(body: dict):
    print("Received initialized notification")
    return {"status": "ok"}


@mcp_method("tools/list")
async def tools_list(body: dict):
    return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"tools": []}}


@mcp_method("resources/list")
async def resources_list(body: dict):
    return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"resources": []}}


@mcp_method("prompts/list")
async def prompts_list(body: dict):
    return {"jsonrpc": "2.0", "id": body.get("id"), "result": {"prompts": []}}


@router.post("/mcp")
async def mcp_handler(request: Request):
    body = await request.json()
    method = body.get("method")

    print(f"Received request: {body}")

    if method in METHOD_HANDLERS:
        response = await METHOD_HANDLERS[method](body)
        print(f"Sending response: {response}")
        return response
    else:
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "error": {"code": -32601, "message": "Method not found"},
        }


app.include_router(router)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
