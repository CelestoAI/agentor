import logging
from typing import Any

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rich import print as print_rich

from .api_router import MCPAPIRouter

logger = logging.getLogger(__name__)


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
        **kwargs,
    ):
        """Initialize LiteMCP server

        Args:
            **kwargs: Additional arguments passed to MCPAPIRouter
        """
        super().__init__(**kwargs)

        # Create FastAPI app
        self.app = FastAPI(
            title=self.name,
            version=self.version,
            description=self.instructions,
        )
        # Include the MCP router
        self.app.include_router(self._fastapi_router)

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        """ASGI interface - delegates to FastAPI app

        This makes LiteMCP a proper ASGI application that can be used with
        any ASGI server (uvicorn, hypercorn, daphne, etc.)
        """
        await self.app(scope, receive, send)

    def serve(
        self,
        host: str = "0.0.0.0",
        port: int = 8000,
        enable_cors: bool = True,
        **uvicorn_kwargs,
    ):
        """Run the server with uvicorn

        Args:
            **uvicorn_kwargs: Additional arguments passed to uvicorn.run()
        """
        if enable_cors:
            self.app.add_middleware(
                CORSMiddleware,
                allow_origins=["*"],
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        uvicorn_config = {"host": host, "port": port, **uvicorn_kwargs}
        print_rich(f"Running MCP server at http://{host}:{port}{self.prefix}")
        uvicorn.run(self.app, **uvicorn_config)

    def run(self, *args, **kwargs):
        """Run the MCP server using uvicorn"""
        logger.warning("This method is deprecated. Use serve() instead.")
        return self.serve(*args, **kwargs)
