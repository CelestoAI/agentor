from typing import Callable, List, Literal, Optional

from a2a import types as a2a_types
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    JSONRPCError,
    JSONRPCRequest,
    JSONRPCResponse,
)
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from agentor.core.schema import (
    JSONRPCReturnCodes,
)


class A2AController(APIRouter):
    """
    A2A Controller for the Agentor framework.

    http://0.0.0.0:8000/.well-known/agent-card.json will return the agent card manifest for this agent following the A2A protocol v0.3.0.
    """

    def __init__(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        url: Optional[str] = None,
        version: str = "0.0.1",
        skills: Optional[List[AgentSkill]] = None,
        capabilities: Optional[AgentCapabilities] = None,
        **kwargs,
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
            url = "http://0.0.0.0:8000"

        super().__init__(tags=["a2a"], **kwargs)

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
            defaultInputModes=["application/json"],
            defaultOutputModes=[],
            supportsAuthenticatedExtendedCard=False,
            signatures=[],
        )

        self._handler = {
            "message/send": None,
            "message/stream": None,
            "tasks/get": None,
            "tasks/cancel": None,
        }

        self.add_api_route(
            "/.well-known/agent-card.json",
            self._agent_card_endpoint,
            methods=["GET", "HEAD", "OPTIONS"],
            response_model=AgentCard,
        )
        self.add_api_route("/", self.run, methods=["POST"])

    async def _agent_card_endpoint(self) -> AgentCard:
        """
        Returns the agent card manifest for this agent following the A2A protocol v0.3.0.
        """
        return JSONResponse(content=self.agent_card.model_dump())

    async def run(self, a2a_request: JSONRPCRequest, request: Request):
        """
        Main JSON-RPC endpoint for A2A protocol operations.
        Supports both streaming and non-streaming responses.
        """
        method = a2a_request.method

        if method == "message/send":
            return await self.message_send(a2a_request)
        elif method == "message/stream":
            return await self.message_stream(a2a_request)
        elif method == "tasks/get":
            return await self.tasks_get(a2a_request)
        elif method == "tasks/cancel":
            return await self.tasks_cancel(a2a_request)
        else:
            return JSONRPCResponse(
                id=a2a_request.id,
                error=JSONRPCError(
                    code=JSONRPCReturnCodes.METHOD_NOT_FOUND,
                    message=f"Method not found: {method}",
                ),
            )

    async def message_stream(self, a2a_request: a2a_types.JSONRPCRequest):
        """
        Streaming implementation of message/stream using Server-Sent Events.

        Returns a stream of JSONRPCResponse objects where result can be:
        - Message: A single agent response message (stream ends immediately)
        - Task: A task object (sent first to establish the task)
        - TaskStatusUpdateEvent: Status updates (working, completed, etc.)
        - TaskArtifactUpdateEvent: Streaming content updates
        """
        send_message_request = a2a_types.SendStreamingMessageRequest.model_validate(
            a2a_request.model_dump()
        )
        handler = self.get_handler("message/stream")
        if handler is None:
            raise ValueError("Handler not implemented for message/stream")
        response = await handler(send_message_request)
        if isinstance(response, StreamingResponse):
            return response
        else:
            raise ValueError(
                f"Invalid response type: {type(response)}. Must be a StreamingResponse."
            )

    async def message_send(self, a2a_request: JSONRPCRequest):
        """
        Non-streaming implementation of message/send.
        """
        handler = self.get_handler("message/send")
        if handler is None:
            raise ValueError("Handler not implemented for message/send")
        response = await handler(a2a_request)
        if isinstance(response, JSONRPCResponse):
            return response
        else:
            raise ValueError(
                f"Invalid response type: {type(response)}. Must be a JSONRPCResponse."
            )

    async def tasks_get(self, a2a_request: JSONRPCRequest):
        handler = self.get_handler("tasks/get")
        if handler is None:
            raise ValueError("Handler not implemented for tasks/get")
        response = await handler(a2a_request)
        if isinstance(response, JSONRPCResponse):
            return response
        else:
            raise ValueError(
                f"Invalid response type: {type(response)}. Must be a JSONRPCResponse."
            )

    async def tasks_cancel(self, a2a_request: JSONRPCRequest):
        handler = self.get_handler("tasks/cancel")
        if handler is None:
            raise ValueError("Handler not implemented for tasks/cancel")
        response = await handler(a2a_request)
        if isinstance(response, JSONRPCResponse):
            return response
        else:
            raise ValueError(
                f"Invalid response type: {type(response)}. Must be a JSONRPCResponse."
            )

    def add_handler(
        self,
        method: Literal["message/send", "message/stream", "tasks/get", "tasks/cancel"],
        handler: Callable,
    ):
        if method not in self._handler:
            raise ValueError(
                f"Invalid method: {method}. Must be one of: {list(self._handler.keys())}."
            )
        self._handler[method] = handler

    def get_handler(
        self,
        method: Literal["message/send", "message/stream", "tasks/get", "tasks/cancel"],
    ) -> Callable:
        if method not in self._handler:
            raise ValueError(
                f"Invalid method: {method}. Must be one of: {list(self._handler.keys())}."
            )
        return self._handler[method]
