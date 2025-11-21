from abc import ABC
from typing import Any, Callable, List, Optional

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

    def run(self, action: str, **kwargs) -> Any:
        """
        Execute a specific action (capability) of the tool.

        Args:
            action: The name of the capability to execute.
            **kwargs: Arguments to pass to the capability.
        """
        if not hasattr(self, action):
            raise ValueError(f"Tool '{self.name}' has no capability '{action}'")

        method = getattr(self, action)
        if getattr(method, "_is_capability", False) is not True:
            raise ValueError(
                f"'{action}' is not a valid capability of tool '{self.name}'"
            )

        return method(**kwargs)

    def to_function_tool(self) -> FunctionTool:
        """Wrap the tool as a FunctionTool for agent consumption."""
        return function_tool(
            self.run,
            name_override=self.name,
            description_override=self.description,
            strict_mode=False,
        )

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
            attr = getattr(self, attr_name)
            if getattr(attr, "_is_capability", False) is True:
                self._mcp_server.tool(name=attr.__name__, description=attr.__doc__)(
                    attr
                )

        # LiteMCP run method handles starting the server
        self._mcp_server.run(port=port)
