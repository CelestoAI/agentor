import inspect
import json
import logging
from contextvars import ContextVar
from dataclasses import dataclass
from typing import (
    Annotated,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    get_args,
    get_origin,
    get_type_hints,
)

from fastapi import APIRouter, Depends, Request
from fastapi.params import Depends as FastAPIDepends
from mcp.types import (
    Icon,
    Implementation,
    InitializeResult,
    PromptsCapability,
    ResourcesCapability,
    ServerCapabilities,
    ToolsCapability,
)

logger = logging.getLogger(__name__)

# Context variable to store the current request
_request_context: ContextVar[Optional[Request]] = ContextVar(
    "request_context", default=None
)


@dataclass
class Context:
    """Context object providing access to request-level data in MCP tools

    This class provides access to HTTP headers and cookies from the incoming request.
    Use it as a dependency in your tool functions to access request context.

    Example:
        @mcp_router.tool()
        def my_tool(location: str, ctx: Context = Depends(get_context)) -> str:
            user_agent = ctx.headers.get("user-agent")
            session_id = ctx.cookies.get("session_id")
            return f"Processing {location}"
    """

    headers: Dict[str, str]
    cookies: Dict[str, str]


def get_context() -> Context:
    """Dependency function to retrieve the current request context

    Returns:
        Context: A Context object with headers and cookies from the current request

    Raises:
        RuntimeError: If called outside of a request context
    """
    request = _request_context.get()
    if request is None:
        # Return empty context if no request is available
        return Context(headers={}, cookies={})

    # Convert Headers to dict for easier access
    headers = dict(request.headers)
    cookies = dict(request.cookies)

    return Context(headers=headers, cookies=cookies)


def get_cookies() -> Dict[str, str]:
    request = _request_context.get()
    if request is None:
        return {}
    return dict(request.cookies)


def get_headers() -> Dict[str, str]:
    request = _request_context.get()
    if request is None:
        return {}
    return dict(request.headers)


def get_token() -> str:
    """Get the token from the request headers.
    Returns:
        The token from the request headers. Doesn't include the "Bearer " prefix.
        Returns None if no token is found.
    """
    headers = get_headers()
    auth = headers.get("Authorization", None) or headers.get("authorization", None)
    if auth is None:
        return None
    return auth.split(" ")[1]


@dataclass
class ToolMetadata:
    func: Callable
    name: str
    description: str
    input_schema: Dict[str, Any]
    dependencies: Optional[Dict[str, FastAPIDepends]] = None


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
        dependencies: Optional[List[Callable]] = None,
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

        self._fastapi_router = APIRouter(dependencies=dependencies)
        self._register_default_handlers()
        self._register_endpoint()

    def _register_endpoint(self):
        """Register the main MCP endpoint"""

        @self._fastapi_router.post(self.prefix)
        async def mcp_handler(request: Request):
            # Store request in context variable for tools to access
            _request_context.set(request)

            try:
                body = await request.json()
                method = body.get("method")
                request_id = body.get("id")

                logger.debug("Received request: %s", body)

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

                        logger.debug("Sending response: %s", response)
                        return response

                    except Exception:
                        logger.exception(
                            "Exception occurred processing MCP method '%s' (id=%s):",
                            method,
                            request_id,
                        )
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
            finally:
                # Clean up context variable
                _request_context.set(None)

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

            if self._extract_dependency_marker(param) is not None:
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

    def _extract_dependency_from_annotation(
        self, annotation: Any
    ) -> Optional[FastAPIDepends]:
        if annotation in (inspect._empty, None):
            return None

        if isinstance(annotation, FastAPIDepends):
            return annotation

        origin = get_origin(annotation)
        if origin is Annotated:
            metadata = get_args(annotation)[1:]
            for meta in metadata:
                if isinstance(meta, FastAPIDepends):
                    return meta

        return None

    def _extract_dependency_marker(
        self, param: inspect.Parameter
    ) -> Optional[FastAPIDepends]:
        marker = self._extract_dependency_from_annotation(param.annotation)
        if marker is not None:
            return marker

        if isinstance(param.default, FastAPIDepends):
            return param.default

        return None

    def _generate_dependencies_from_function(
        self, func: Callable
    ) -> Dict[str, Depends]:
        """Generate dependencies from function signature using Depends"""
        sig = inspect.signature(func)
        dependencies: Dict[str, FastAPIDepends] = {}

        for param_name, param in sig.parameters.items():
            dependency_marker = self._extract_dependency_marker(param)
            if dependency_marker is not None:
                dependencies[param_name] = dependency_marker

        return dependencies

    async def _resolve_dependency_marker(
        self,
        dependency: FastAPIDepends,
        stack: Optional[Set[Callable]] = None,
    ) -> Any:
        dep_callable = dependency.dependency
        if dep_callable is None:
            raise ValueError("Dependency marker is missing a callable")

        return await self._call_with_dependencies(dep_callable, stack)

    async def _call_with_dependencies(
        self,
        func: Callable,
        stack: Optional[Set[Callable]] = None,
    ) -> Any:
        stack = stack or set()
        if func in stack:
            raise RuntimeError(
                f"Circular dependency detected while resolving '{func.__name__}'"
            )

        stack.add(func)

        try:
            sig = inspect.signature(func)
            kwargs: Dict[str, Any] = {}

            for param_name, param in sig.parameters.items():
                marker = self._extract_dependency_marker(param)
                if marker is not None:
                    kwargs[param_name] = await self._resolve_dependency_marker(
                        marker, stack
                    )
                    continue

                if param.default != inspect.Parameter.empty:
                    continue

                raise ValueError(
                    f"Cannot resolve parameter '{param_name}' for dependency '{func.__name__}'"
                )

            value = func(**kwargs)
            if inspect.isawaitable(value):
                value = await value

            return value
        finally:
            stack.remove(func)

    async def _resolve_dependencies(
        self, dependencies: Dict[str, FastAPIDepends]
    ) -> Dict[str, Any]:
        """Resolve dependency callables to concrete values"""

        resolved: Dict[str, Any] = {}

        for name, dependency in dependencies.items():
            resolved[name] = await self._resolve_dependency_marker(dependency, set())

        return resolved

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
            logger.debug("Client initialized")
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
            arguments = params.get("arguments") or {}

            if tool_name not in self.tools:
                return {
                    "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                    "isError": True,
                }

            try:
                tool_meta = self.tools[tool_name]
                dependencies = tool_meta.dependencies or {}
                resolved_dependencies = (
                    await self._resolve_dependencies(dependencies)
                    if dependencies
                    else {}
                )
                call_kwargs = {**arguments, **resolved_dependencies}

                if inspect.iscoroutinefunction(tool_meta.func):
                    result = await tool_meta.func(**call_kwargs)
                else:
                    result = tool_meta.func(**call_kwargs)

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
                logger.exception("Error executing tool '%s': %s", tool_name, str(e))
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

            except Exception as e:
                logger.exception("Error reading resource '%s': %s", uri, str(e))
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

            except Exception as e:
                logger.exception("Error executing prompt '%s': %s", prompt_name, str(e))
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
            tool_description = description or (func.__doc__ or "").strip()
            schema = input_schema or self._generate_schema_from_function(func)
            dependencies = self._generate_dependencies_from_function(func)
            self.tools[tool_name] = ToolMetadata(
                func=func,
                name=tool_name,
                description=tool_description,
                input_schema=schema,
                dependencies=dependencies,
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
            resource_description = description or func.__doc__ or ""

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
