from typing import Optional, List, AsyncGenerator
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .schema import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
)


router = APIRouter(prefix="/a2a")


class A2AController(APIRouter):
    """
    A2A Controller for the Agentor framework.

    http://0.0.0.0:8000/a2a/.well-known/agent-card.json will return the agent card manifest for this agent following the A2A protocol v0.3.0.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        version: str = "0.0.1",
        skills: Optional[List[AgentSkill]] = None,
        capabilities: Optional[AgentCapabilities] = None,
    ):
        if skills is None:
            skills = []
        if capabilities is None:
            capabilities = AgentCapabilities(
                streaming=True, statefulness=True, asyncProcessing=True
            )

        if name is None:
            name = "Agentor"
        if description is None:
            description = "Agentor is a framework for building, prototyping and deploying AI Agents."
        if url is None:
            url = "https://docs.celesto.ai"

        super().__init__(prefix="/a2a", tags=["a2a"])

        self.agent_card = AgentCard(
            name=name,
            description=description,
            url=url,
            version=version,
            skills=skills,
            capabilities=capabilities,
            additionalInterfaces=[],
            securitySchemes={},
            security=[],
            defaultInputModes=["text/plain", "application/json"],
            defaultOutputModes=[],
            supportsAuthenticatedExtendedCard=False,
            signatures=[],
        )

        self.add_api_route(
            "/.well-known/agent-card.json",
            self._agent_card_endpoint,
            methods=["GET", "HEAD", "OPTIONS"],
            response_model=AgentCard,
        )
        self.add_api_route("", self.run, methods=["POST"])

    async def _agent_card_endpoint(self) -> AgentCard:
        """
        Returns the agent card manifest for this agent following the A2A protocol v0.3.0.
        """
        return self.agent_card

    async def run(self, a2a_request: JSONRPCRequest, request: Request):
        """
        Main JSON-RPC endpoint for A2A protocol operations.
        Supports both streaming and non-streaming responses.
        """
        method = a2a_request.method

        # Check if client wants streaming via Accept header
        accept_header = request.headers.get("accept", "")
        wants_streaming = "text/event-stream" in accept_header

        if method == "message/send":
            if wants_streaming:
                return await self.message_send_stream(a2a_request)
            else:
                return await self.message_send(a2a_request)
        elif method == "tasks/get":
            return await self.tasks_get(a2a_request)
        elif method == "tasks/cancel":
            return await self.tasks_cancel(a2a_request)
        else:
            return JSONRPCResponse(
                id=a2a_request.id,
                error=JSONRPCError(
                    code=-32601,
                    message=f"Method not found: {method}",
                ),
            )

    async def message_send_stream(self, a2a_request: JSONRPCRequest):
        """
        Streaming implementation of message/send using Server-Sent Events.
        """

        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                # Send initial response
                response = JSONRPCResponse(
                    id=a2a_request.id,
                    result={
                        "status": "processing",
                        "message": "Message received and processing started",
                    },
                )
                yield f"data: {json.dumps(response.model_dump())}\n\n"

                # Process the message (implement your logic here)
                # For now, we'll send a simple completion message
                final_response = JSONRPCResponse(
                    id=a2a_request.id,
                    result={
                        "status": "completed",
                        "message": "This is a placeholder response. Implement your agent logic here.",
                        "content": "Hello! I received your message.",
                    },
                )
                yield f"data: {json.dumps(final_response.model_dump())}\n\n"

            except Exception as e:
                error_response = JSONRPCResponse(
                    id=a2a_request.id,
                    error=JSONRPCError(
                        code=-32603, message=f"Internal error: {str(e)}"
                    ),
                )
                yield f"data: {json.dumps(error_response.model_dump())}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )

    async def message_send(self, a2a_request: JSONRPCRequest):
        """
        Non-streaming implementation of message/send.
        """
        return JSONRPCResponse(
            id=a2a_request.id,
            result={
                "status": "completed",
                "message": "This is a placeholder response. Implement your agent logic here.",
                "content": "Hello! I received your message.",
            },
        )

    async def tasks_get(self, a2a_request: JSONRPCRequest):
        return JSONRPCResponse(
            id=a2a_request.id,
            error=JSONRPCError(
                code=-32601,
                message="tasks/get not implemented yet",
            ),
        )

    async def tasks_cancel(self, a2a_request: JSONRPCRequest):
        return JSONRPCResponse(
            id=a2a_request.id,
            error=JSONRPCError(
                code=-32601,
                message="tasks/cancel not implemented yet",
            ),
        )
