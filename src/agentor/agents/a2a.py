from typing import Optional, List, AsyncGenerator
import json
from datetime import datetime
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from .schema import (
    JSONRPCReturnCodes,
)

from a2a.types import (
    AgentCard,
    AgentCapabilities,
    AgentSkill,
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    Message,
    Part,
    Task,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)


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

    async def message_stream(self, a2a_request: JSONRPCRequest):
        """
        Streaming implementation of message/stream using Server-Sent Events.
        Returns a stream of JSONRPCResponse objects where result can be:
        - Message: An agent response message
        - Task: A task object
        - TaskStatusUpdateEvent: Status update for a task
        - TaskArtifactUpdateEvent: Artifact update for a task
        """

        async def event_generator() -> AsyncGenerator[str, None]:
            task_id = f"task_{int(datetime.utcnow().timestamp())}"
            context_id = f"ctx_{int(datetime.utcnow().timestamp())}"

            # 1. Send initial task creation
            task = Task(
                id=task_id,
                contextId=context_id,
                status=TaskStatus(state=TaskState.working),
            )
            response = JSONRPCResponse(id=a2a_request.id, result=task.model_dump())
            yield f"data: {json.dumps(response.model_dump())}\n\n"

            # 2. Send message response
            message = Message(
                messageId=f"msg_{int(datetime.utcnow().timestamp())}",
                role="assistant",
                parts=[
                    Part(
                        type="text",
                        text="Hello! This is a placeholder response.",
                    )
                ],
            )
            response = JSONRPCResponse(id=a2a_request.id, result=message.model_dump())
            yield f"data: {json.dumps(response.model_dump())}\n\n"

            # 3. Send final status update
            final_status = TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
            response = JSONRPCResponse(
                id=a2a_request.id, result=final_status.model_dump()
            )
            yield f"data: {json.dumps(response.model_dump())}\n\n"

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
                code=JSONRPCReturnCodes.SERVER_ERROR_NOT_IMPLEMENTED,
                message="tasks/get not implemented yet",
            ),
        )

    async def tasks_cancel(self, a2a_request: JSONRPCRequest):
        return JSONRPCResponse(
            id=a2a_request.id,
            error=JSONRPCError(
                code=JSONRPCReturnCodes.SERVER_ERROR_NOT_IMPLEMENTED,
                message="tasks/cancel not implemented yet",
            ),
        )
