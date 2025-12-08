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

    def _get_tool(self, name: str) -> Callable:
        """Get a function marked as a tool capability."""
        func = getattr(self, name)
        if getattr(func, "_is_capability", False) is not True:
            raise ValueError(f"Tool '{name}' doesn't exist for the class '{self.name}'")
        return func

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

    def run(self):
        raise NotImplementedError(
            "This method is dynamically registered using the BaseTool.from_function method."
        )

    @staticmethod
    def from_function(func: Callable) -> "BaseTool":
        """Register a function as a tool capability and access using the run method.

        Args:
            func: The function to be registered.

        Example:
            >>> from agentor.tools.base import BaseTool
            >>> def weather_tool(city: str):
            >>>    "This function returns the weather of the city."
            >>>    return f"Weather in {city} is warm and sunny."
            >>> tool = BaseTool.from_function(weather_tool)
            >>> tool.run("London")  # Output: Weather in London is warm and sunny.
        """

        class NewDynamicTool(BaseTool):
            name = func.__name__
            description = func.__doc__

            def run(self, *args, **kwargs) -> Optional[str]:
                return func(*args, **kwargs)

        return NewDynamicTool()
