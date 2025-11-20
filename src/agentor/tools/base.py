import functools
from abc import ABC, abstractmethod
from typing import Any, Optional, Type

from agents import FunctionTool, function_tool
from pydantic import BaseModel

from agentor.mcp.server import LiteMCP


class BaseTool(ABC):
    """
    Base class for all tools in Agentor.
    Supports both local execution and MCP serving.
    """

    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._mcp_server: Optional[LiteMCP] = None

    @abstractmethod
    def run(self, *args, **kwargs) -> Any:
        """Execute the tool logic."""
        pass

    def to_function_tool(self) -> FunctionTool:
        """Convert the tool to an OpenAI-compatible FunctionTool."""

        # If args_schema is provided, we can use it for validation/schema generation
        # For now, we'll rely on the function signature of the run method
        # or a wrapper that uses the schema if implemented.

        # We wrap the run method to ensure it has the correct metadata
        # We use functools.wraps to preserve the signature which is crucial for schema generation

        @functools.wraps(self.run)
        def func(*args, **kwargs):
            return self.run(*args, **kwargs)

        func.__name__ = self.name
        func.__doc__ = self.description

        return function_tool(func)

    def serve(self, name: Optional[str] = None, port: int = 8000):
        """Serve the tool as an MCP server using LiteMCP."""
        server_name = name or self.name
        self._mcp_server = LiteMCP(name=server_name, version="1.0.0")

        # Register the tool with LiteMCP
        # We need to bind the run method to the server
        self._mcp_server.tool(name=self.name, description=self.description)(self.run)

        # LiteMCP run method handles starting the server
        self._mcp_server.run(port=port)
