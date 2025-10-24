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


@dataclass
class ToolMetadata:
    """Metadata for a registered tool"""

    func: Callable
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class ResourceMetadata:
    """Metadata for a registered resource"""

    func: Callable
    uri: str
    name: str
    description: Optional[str]
    mime_type: Optional[str]


@dataclass
class PromptMetadata:
    """Metadata for a registered prompt"""

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
                try:
                    # Call the handler and get the result
                    result = await self.method_handlers[method](body)

                    # Auto-wrap in JSON-RPC format if not already wrapped
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

                except Exception as e:
                    # Return JSON-RPC error
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"Internal error: {str(e)}",
                        },
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": "Method not found"},
                }

    def _python_type_to_json_schema(self, python_type: type) -> str:
        """Convert Python type to JSON schema type"""
        type_map = {
            str: "string",
            int: "integer",
            float: "number",
            bool: "boolean",
            list: "array",
            dict: "object",
        }
        return type_map.get(python_type, "string")

    def _generate_schema_from_function(self, func: Callable) -> Dict[str, Any]:
        """Generate JSON schema from function signature and type hints"""
        sig = inspect.signature(func)
        type_hints = get_type_hints(func)

        properties = {}
        required = []

        for param_name, param in sig.parameters.items():
            if param_name == "self":
                continue

            param_type = type_hints.get(param_name, str)
            json_type = self._python_type_to_json_schema(param_type)

            properties[param_name] = {"type": json_type}

            # Add description from docstring if available
            if func.__doc__:
                # Simple docstring parsing (could be enhanced)
                properties[param_name]["description"] = f"Parameter: {param_name}"

            # If no default value, it's required
            if param.default == inspect.Parameter.empty:
                required.append(param_name)

        schema = {
            "type": "object",
            "properties": properties,
        }

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

        # Tools handlers
        @self.method("tools/list")
        async def default_tools_list(body: dict):
            tools_list = []
            for tool_name, tool_meta in self.tools.items():
                tools_list.append(
                    {
                        "name": tool_meta.name,
                        "description": tool_meta.description,
                        "inputSchema": tool_meta.input_schema,
                    }
                )
            return {"tools": tools_list}

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

                # Call the tool function
                if inspect.iscoroutinefunction(tool_meta.func):
                    result = await tool_meta.func(**arguments)
                else:
                    result = tool_meta.func(**arguments)

                # Format the result
                if isinstance(result, str):
                    content = [{"type": "text", "text": result}]
                elif isinstance(result, list):
                    content = result
                elif isinstance(result, dict):
                    if "content" in result:
                        content = result["content"]
                    else:
                        content = [{"type": "text", "text": json.dumps(result)}]
                else:
                    content = [{"type": "text", "text": str(result)}]

                return {"content": content}

            except Exception as e:
                return {
                    "content": [{"type": "text", "text": f"Error: {str(e)}"}],
                    "isError": True,
                }

        # Resources handlers
        @self.method("resources/list")
        async def default_resources_list(body: dict):
            resources_list = []
            for uri, resource_meta in self.resources.items():
                resources_list.append(
                    {
                        "uri": resource_meta.uri,
                        "name": resource_meta.name,
                        "description": resource_meta.description,
                        "mimeType": resource_meta.mime_type,
                    }
                )
            return {"resources": resources_list}

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

                # Format result as resource contents
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

        # Prompts handlers
        @self.method("prompts/list")
        async def default_prompts_list(body: dict):
            prompts_list = []
            for prompt_name, prompt_meta in self.prompts.items():
                prompts_list.append(
                    {
                        "name": prompt_meta.name,
                        "description": prompt_meta.description,
                        "arguments": prompt_meta.arguments or [],
                    }
                )
            return {"prompts": prompts_list}

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

                # Format as prompt messages
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
        """Decorator to register a tool (inspired by FastMCP)"""

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

            # Generate arguments schema from function if not provided
            if arguments is None and func:
                sig = inspect.signature(func)
                args_list = []
                for param_name, param in sig.parameters.items():
                    if param_name != "self":
                        args_list.append(
                            {
                                "name": param_name,
                                "description": f"Parameter: {param_name}",
                                "required": param.default == inspect.Parameter.empty,
                            }
                        )
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
