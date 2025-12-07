from abc import ABC
from typing import Callable, List, Optional

from agents import FunctionTool, function_tool

from agentor.mcp.server import LiteMCP


def capability(func: Callable):
    """Decorator to mark a method as a tool capability."""
    func._is_capability = True
    return func


class BaseTool(ABC):
    """
    Base class for all tools in Agentor.
    Supports both local execution and MCP serving.
    """

    name: str
    description: str

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._mcp_server: Optional[LiteMCP] = None

    def list_capabilities(self) -> List[str]:
        """List all capabilities of the tool."""
        return [
            attr
            for attr in dir(self)
            if getattr(getattr(self, attr), "_is_capability", False) is True
        ]

    def _get_capability(self, name: str) -> Callable:
        """Get a capability of the tool."""
        capability = getattr(self, name)
        if getattr(capability, "_is_capability", False) is not True:
            raise ValueError(
                f"Capability '{name}' is not a valid capability of tool '{self.name}'"
            )
        return capability

    def to_openai_function(self) -> List[FunctionTool]:
        """Convert all capabilities to OpenAI-compatible FunctionTools."""
        tools = []

        # Check for capabilities
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if getattr(attr, "_is_capability", False) is True:
                tools.append(function_tool(attr, strict_mode=False))

        return tools

    def serve(self, name: Optional[str] = None, port: int = 8000):
        """Serve the tool as an MCP server using LiteMCP."""
        server_name = name or self.name
        self._mcp_server = LiteMCP(name=server_name, version="1.0.0")

        # Register all capabilities with LiteMCP
        for attr_name in dir(self):
            func = getattr(self, attr_name)
            if getattr(func, "_is_capability", False) is True:
                self._mcp_server.tool(name=func.__name__, description=func.__doc__)(
                    func
                )

        # LiteMCP run method handles starting the server
        self._mcp_server.run(port=port)
