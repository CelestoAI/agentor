from typing import Optional
from typing import List
from fastapi import APIRouter, Request
from .schema import AgentCard, AgentCapabilities, AgentSkill, JSONRPCError


router = APIRouter(prefix="/a2a")


class A2AController(APIRouter):
    def __init__(
        self,
        name: str,
        description: str,
        url: str,
        version: str = "0.0.1",
        skills: Optional[List[AgentSkill]] = None,
        capabilities: Optional[AgentCapabilities] = AgentCapabilities(
            streaming=True, statefulness=True, asyncProcessing=True
        ),
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
            url = "https://agentor.ai"

        # @router.get("/.well-known/agent-card.json", response_model=AgentCard)
        super().__init__(prefix="/a2a", tags=["a2a"])
        self.name = name
        self.description = description
        self.url = url
        self.version = version
        self.skills = skills
        self.capabilities = capabilities
        self.add_api_route(
            "/.well-known/agent-card.json",
            self.agent_card,
            methods=["GET", "HEAD", "OPTIONS"],
            response_model=AgentCard,
        )
        self.add_api_route("", self.run, methods=["POST", "GET"])

    async def agent_card(self) -> AgentCard:
        """
        Returns the agent card manifest for this agent following the A2A protocol v0.3.0.
        """
        return AgentCard(
            name=self.name,
            description=self.description,
            url=self.url,
            version=self.version,
            skills=self.skills,
            capabilities=self.capabilities,
        )

    async def run(self, request: Request):
        request_data = await request.body()
        return
        print(request_data)
        breakpoint()
        method = request.method
        params = request.params
        id = request.id
        if method == "message/send":
            return await self.message_send(params)
        elif method == "tasks/get":
            return await self.tasks_get(params)
        else:
            return JSONRPCError(code=-32601, message="Method not found")
