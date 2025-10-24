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
from typing import Callable, Dict, Optional, List, Any, get_type_hints
import inspect
import json
from dataclasses import dataclass
import logging

@dataclass
class ToolMetadata:
    func: Callable
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class ResourceMetadata:
    func: Callable
    uri: str
    name: str
    description: Optional[str]
    mime_type: Optional[str]


@dataclass
class PromptMetadata:
    func: Callable
    name: str
    description: Optional[str]
    arguments: Optional[List[Dict[str, Any]]]


class MCPAPIRouter:
    """Router for MCP JSON-RPC methods with FastAPI-like decorator API

    Inspired by FastMCP from the official MCP Python SDK:
    https://github.com/modelcontextprotocol/python-sdk
    """

    def __init__(
        self,
        prefix: str = "/mcp",
        name: str = "agentor-mcp-server",
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

        # Storage for registered items
        self.method_handlers: Dict[str, Callable] = {}
        self.tools: Dict[str, ToolMetadata] = {}
        self.resources: Dict[str, ResourceMetadata] = {}
        self.prompts: Dict[str, PromptMetadata] = {}

        self._fastapi_router = APIRouter()
        self._register_default_handlers()
        self._register_endpoint()

    def _register_endpoint(self):
        """Register the main MCP endpoint"""

        @self._fastapi_router.post(self.prefix)
        async def mcp_handler(request: Request):
            body = await request.json()
            method = body.get("method")
            request_id = body.get("id")

            print(f"Received request: {body}")

            if method in self.method_handlers:
                try:
                    result = await self.method_handlers[method](body)

                    if isinstance(result, dict) and "jsonrpc" in result:
                        response = result
                    else:
                        response = {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "result": result,
                        }

                    print(f"Sending response: {response}")
                    return response

                    logging.exception("Exception occurred processing MCP method '%s' (id=%s):", method, request_id)
                except Exception as e:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": "Internal error",
                        },
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "Method not found"},
                }

    def _generate_schema_from_function(self, func: Callable) -> Dict[str, Any]:
        """Generate JSON schema from function signature"""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties = {}
        required = []

        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name, str)
            properties[param_name] = {
                "type": type_map.get(param_type, "string"),
                "description": f"Parameter: {param_name}",
            }

            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {"type": "object", "properties": properties}
        if required:
            schema["required"] = required

        return schema

    def _register_default_handlers(self):
        """Register default MCP handlers"""

        @self.method("initialize")
        async def default_initialize(body: dict):
            params = body.get("params", {})
            result = InitializeResult(
                protocolVersion=params.get("protocolVersion"),
                capabilities=ServerCapabilities(
                    tools=ToolsCapability(listChanged=True) if self.tools else None,
                    resources=ResourcesCapability(listChanged=True)
                    if self.resources
                    else None,
                    prompts=PromptsCapability(listChanged=True)
                    if self.prompts
                    else None,
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

        @self.method("notifications/initialized")
        async def default_initialized_notification(body: dict):
            print("Client initialized")
            return {}

        @self.method("ping")
        async def default_ping(body: dict):
            return {}

        # Tool handlers
        @self.method("tools/list")
        async def default_tools_list(body: dict):
            return {
                "tools": [
                    {
                        "name": meta.name,
                        "description": meta.description,
                        "inputSchema": meta.input_schema,
                    }
                    for meta in self.tools.values()
                ]
            }

        @self.method("tools/call")
        async def default_tools_call(body: dict):
            params = body.get("params", {})
            tool_name = params.get("name")
            arguments = params.get("arguments", {})

            if tool_name not in self.tools:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True,
                }

            try:
                tool_meta = self.tools[tool_name]

                if inspect.iscoroutinefunction(tool_meta.func):
                    result = await tool_meta.func(**arguments)
                else:
                    result = tool_meta.func(**arguments)

                if isinstance(result, str):
                    content = [{"type": "text", "text": result}]
                elif isinstance(result, list):
                    content = result
                elif isinstance(result, dict):
                    content = result.get(
                        "content", [{"type": "text", "text": json.dumps(result)}]
                    )
                else:
                    content = [{"type": "text", "text": str(result)}]

                return {"content": content}

            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                }

        # Resource handlers
        @self.method("resources/list")
        async def default_resources_list(body: dict):
            return {
                "resources": [
                    {
                        "uri": meta.uri,
                        "name": meta.name,
                        "description": meta.description,
                        "mimeType": meta.mime_type,
                    }
                    for meta in self.resources.values()
                ]
            }

        @self.method("resources/read")
        async def default_resources_read(body: dict):
            params = body.get("params", {})
            uri = params.get("uri")

            if uri not in self.resources:
                return {"contents": [], "isError": True}

            try:
                resource_meta = self.resources[uri]

                if inspect.iscoroutinefunction(resource_meta.func):
                    result = await resource_meta.func(uri)
                else:
                    result = resource_meta.func(uri)

                if isinstance(result, str):
                    contents = [
                        {
                            "uri": uri,
                            "mimeType": resource_meta.mime_type or "text/plain",
                            "text": result,
                        }
                    ]
                elif isinstance(result, dict):
                    contents = [result]
                else:
                    contents = result

                return {"contents": contents}

            except Exception:
                return {"contents": [], "isError": True}

        @self.method("resources/templates/list")
        async def default_resources_templates_list(body: dict):
            return {"resourceTemplates": []}

        # Prompt handlers
        @self.method("prompts/list")
        async def default_prompts_list(body: dict):
            return {
                "prompts": [
                    {
                        "name": meta.name,
                        "description": meta.description,
                        "arguments": meta.arguments or [],
                    }
                    for meta in self.prompts.values()
                ]
            }

        @self.method("prompts/get")
        async def default_prompts_get(body: dict):
            params = body.get("params", {})
            prompt_name = params.get("name")
            arguments = params.get("arguments", {})

            if prompt_name not in self.prompts:
                return {"messages": [], "isError": True}

            try:
                prompt_meta = self.prompts[prompt_name]

                if inspect.iscoroutinefunction(prompt_meta.func):
                    result = await prompt_meta.func(**arguments)
                else:
                    result = prompt_meta.func(**arguments)

                if isinstance(result, str):
                    messages = [
                        {"role": "user", "content": {"type": "text", "text": result}}
                    ]
                elif isinstance(result, list):
                    messages = result
                else:
                    messages = [result]

                return {"description": prompt_meta.description, "messages": messages}

            except Exception:
                return {"messages": [], "isError": True}

    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        """Decorator to register a tool"""

        def decorator(func: Callable):
            tool_name = name or func.__name__
            tool_description = (
                description or (func.__doc__ or f"Tool: {tool_name}").strip()
            )
            schema = input_schema or self._generate_schema_from_function(func)

            self.tools[tool_name] = ToolMetadata(
                func=func,
                name=tool_name,
                description=tool_description,
                input_schema=schema,
            )
            return func

        return decorator

    def resource(
        self,
        uri: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mime_type: Optional[str] = None,
    ):
        """Decorator to register a resource"""

        def decorator(func: Callable):
            resource_name = name or uri
            resource_description = description or func.__doc__ or f"Resource: {uri}"

            self.resources[uri] = ResourceMetadata(
                func=func,
                uri=uri,
                name=resource_name,
                description=resource_description.strip(),
                mime_type=mime_type,
            )
            return func

        return decorator

    def prompt(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        arguments: Optional[List[Dict[str, Any]]] = None,
    ):
        """Decorator to register a prompt"""

        def decorator(func: Callable):
            prompt_name = name or func.__name__
            prompt_description = (
                description or (func.__doc__ or f"Prompt: {prompt_name}").strip()
            )

            if arguments is None:
                sig = inspect.signature(func)
                args_list = [
                    {
                        "name": param_name,
                        "description": f"Parameter: {param_name}",
                        "required": param.default == inspect.Parameter.empty,
                    }
                    for param_name, param in sig.parameters.items()
                    if param_name != "self"
                ]
                prompt_arguments = args_list if args_list else None
            else:
                prompt_arguments = arguments

            self.prompts[prompt_name] = PromptMetadata(
                func=func,
                name=prompt_name,
                description=prompt_description,
                arguments=prompt_arguments,
            )
            return func

        return decorator

    def method(self, method_name: str):
        """Decorator to register custom MCP method handlers"""

        def decorator(func: Callable):
            self.method_handlers[method_name] = func
            return func

        return decorator

    def get_fastapi_router(self) -> APIRouter:
        """Get the underlying FastAPI router"""
        return self._fastapi_router
