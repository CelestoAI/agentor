from fastapi import APIRouter, Request
from mcp.types import (
    Icon,
    Implementation,
    InitializeResult,
    ServerCapabilities,
    ToolsCapability,
    ResourcesCapability,
    PromptsCapability,
)
from typing import Callable, Dict, Optional, List


class MCPAPIRouter:
    """Router for MCP JSON-RPC methods with FastAPI-like decorator API"""

    def __init__(
        self,
        prefix: str = "/mcp",
        name: str = "mcp-server",
        version: str = "0.1.0",
        instructions: Optional[str] = None,
        website_url: Optional[str] = None,
        icons: Optional[List[Icon]] = None,
    ):
        self.prefix = prefix
        self.name = name
        self.version = version
        self.instructions = instructions
        self.website_url = website_url
        self.icons = icons
        self.method_handlers: Dict[str, Callable] = {}
        self._fastapi_router = APIRouter()

        # Register default handlers
        self._register_default_handlers()

        # Register the main MCP endpoint
        @self._fastapi_router.post(prefix)
        async def mcp_handler(request: Request):
            body = await request.json()
            method = body.get("method")
            request_id = body.get("id")

            print(f"Received request: {body}")

            if method in self.method_handlers:
                # Call the handler and get the result
                result = await self.method_handlers[method](body)

                # Auto-wrap in JSON-RPC format if not already wrapped
                if isinstance(result, dict) and "jsonrpc" in result:
                    # Already in JSON-RPC format, return as-is
                    response = result
                else:
                    # Wrap the result in JSON-RPC format
                    response = {"jsonrpc": "2.0", "id": request_id, "result": result}

                print(f"Sending response: {response}")
                return response
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "Method not found"},
                }

    def _register_default_handlers(self):
        """Register default MCP handlers that can be overridden"""

        # Default initialize handler
        @self.method("initialize")
        async def default_initialize(body: dict):
            params = body.get("params", {})

            result = InitializeResult(
                protocolVersion=params.get("protocolVersion"),
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=True),
                    resources=ResourcesCapability(listChanged=True),
                    prompts=PromptsCapability(listChanged=True),
                ),
                serverInfo=Implementation(
                    name=self.name,
                    version=self.version,
                    websiteUrl=self.website_url,
                    icons=self.icons,
                ),
                instructions=self.instructions,
            )

            return result.model_dump(exclude_none=True)

        # Default notifications/initialized handler
        @self.method("notifications/initialized")
        async def default_initialized_notification(body: dict):
            print("Received initialized notification")
            return {"status": "ok"}

        # Default tools/list handler
        @self.method("tools/list")
        async def default_tools_list(body: dict):
            return {"tools": []}

        # Default resources/list handler
        @self.method("resources/list")
        async def default_resources_list(body: dict):
            return {"resources": []}

        # Default resources/templates/list handler
        @self.method("resources/templates/list")
        async def default_resources_templates_list(body: dict):
            return {"resourceTemplates": []}

        # Default prompts/list handler
        @self.method("prompts/list")
        async def default_prompts_list(body: dict):
            return {"prompts": []}

    def method(self, method_name: str):
        """Decorator to register MCP method handlers

        The handler should return just the result data, not the full JSON-RPC response.
        The router will automatically wrap it in the proper JSON-RPC format.

        This can be used to override default handlers or add new ones.

        Usage:
            @router.method("tools/list")
            async def handle_tools_list(body: dict):
                return {"tools": [{"name": "my_tool", ...}]}
        """

        def decorator(func: Callable):
            self.method_handlers[method_name] = func
            return func

        return decorator

    def get_fastapi_router(self) -> APIRouter:
        """Get the underlying FastAPI router"""
        return self._fastapi_router
