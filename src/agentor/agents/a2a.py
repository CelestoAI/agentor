from typing import Optional
from typing import List
from fastapi import APIRouter, Request
from .schema import AgentCard, AgentCapabilities, AgentSkill, JSONRPCError


router = APIRouter(prefix="/a2a")


class A2AController(APIRouter):
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
        self.add_api_route("", self.run, methods=["POST", "GET"])

    async def _agent_card_endpoint(self) -> AgentCard:
        """
        Returns the agent card manifest for this agent following the A2A protocol v0.3.0.
        """
        return self.agent_card

    async def run(self, request: Request):
        request_data = await request.body()
        return
        print(request_data)
        method = request.method
        params = request.params
        if method == "message/send":
            return await self.message_send(params)
        elif method == "tasks/get":
            return await self.tasks_get(params)
        else:
            return JSONRPCError(code=-32601, message="Method not found")
