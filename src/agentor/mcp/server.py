from .api_router import MCPAPIRouter
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from typing import Any


class LiteMCP(MCPAPIRouter):
    """ASGI-compatible MCP server built on FastAPI

    This class can be used directly as an ASGI application or run with uvicorn.

    Example:
        # As ASGI app
        app = LiteMCP()

        # Run with uvicorn
        app.run()

        # Or use with uvicorn CLI
        # uvicorn module:app
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        enable_cors: bool = True,
        **kwargs,
    ):
        """Initialize LiteMCP server

        Args:
            host: Host to bind to when using run()
            port: Port to bind to when using run()
            enable_cors: Whether to enable CORS middleware
            **kwargs: Additional arguments passed to MCPAPIRouter
        """
        super().__init__(**kwargs)
        self.host = host
        self.port = port

        # Create FastAPI app
        self.app = FastAPI(
            title=self.name,
            version=self.version,
            description=self.instructions,
        )

        # Add CORS middleware if enabled
        if enable_cors:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )

        # Include the MCP router
        self.app.include_router(self._fastapi_router)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """ASGI interface - delegates to FastAPI app

        This makes LiteMCP a proper ASGI application that can be used with
        any ASGI server (uvicorn, hypercorn, daphne, etc.)
        """
        await self.app(scope, receive, send)

    def run(self, **uvicorn_kwargs):
        """Run the server with uvicorn

        Args:
            **uvicorn_kwargs: Additional arguments passed to uvicorn.run()
        """
        uvicorn_config = {"host": self.host, "port": self.port, **uvicorn_kwargs}
        uvicorn.run(self.app, **uvicorn_config)
