import json
import logging
import os
import uuid
from typing import (
    Any,
    AsyncGenerator,
    AsyncIterator,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
)

import uvicorn
from a2a import types as a2a_types
from a2a.types import JSONRPCResponse, Task, TaskState, TaskStatus
from agents import Agent, FunctionTool, Runner, function_tool
from agents.mcp import MCPServerStreamableHttp
from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from agentor.agents.a2a import A2AController, AgentSkill
from agentor.output_text_formatter import AgentOutput, format_stream_events
from agentor.prompts import THINKING_PROMPT, render_prompt
from agentor.tools.registry import CelestoConfig, ToolRegistry

logger = logging.getLogger(__name__)


CELESTO_BASE_URL = os.environ.get("CELESTO_BASE_URL", "https://api.celesto.ai/v1")
CELESTO_API_KEY = os.environ.get("CELESTO_API_KEY")


class ToolFunctionParameters(TypedDict, total=False):
    type: str
    properties: Dict[str, Any]
    required: List[str]


class ToolFunction(TypedDict, total=False):
    name: str
    description: Optional[str]
    parameters: ToolFunctionParameters


class Tool(TypedDict):
    type: Literal["function"]
    function: ToolFunction


@function_tool(name_override="get_weather")
def get_dummy_weather(city: str) -> str:
    """Returns the dummy weather in the given city."""
    return f"The dummy weather in {city} is sunny"


class APIInputRequest(BaseModel):
    input: Union[str, List[Dict[str, str]]]
    stream: bool = False


class AgentorBase:
    def __init__(
        self,
        name: str,
        instructions: Optional[str],
        model: Optional[str],
    ):
        self.agent = None
        self.name = name
        self.instructions = instructions
        self.model = model

        if os.environ.get("OPENAI_API_KEY") is None:
            raise ValueError("""OPENAI_API_KEY is required to use the Agentor.
            Please set the OPENAI_API_KEY environment variable.""")


class Agentor(AgentorBase):
    """
    Build an Agent, connect tools, and serve as an API in just few lines of code.

    Example:
        >>> from agentor import Agentor
        >>> agent = Agentor(name="Weather Agent", model="gpt-5-mini", tools=["celesto/weather"])
        >>> result = agent.run("What is the weather in London?")
        >>> print(result)

        >>> # Serve the Agent as an API
        >>> agent.serve(port=8000)
    """

    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str] = "gpt-5-nano",
        tools: Optional[List[Union[FunctionTool, str, MCPServerStreamableHttp]]] = None,
        debug: bool = False,
    ):
        super().__init__(name, instructions, model)
        tools = tools or []

        resolved_tools: List[FunctionTool] = []
        mcp_servers: List[MCPServerStreamableHttp] = []

        for tool in tools:
            if isinstance(tool, str):
                resolved_tools.append(ToolRegistry.get(tool)["tool"])
            elif isinstance(tool, FunctionTool):
                resolved_tools.append(tool)
            elif isinstance(tool, MCPServerStreamableHttp):
                mcp_servers.append(tool)
            else:
                raise TypeError(
                    f"Unsupported tool type '{type(tool).__name__}'. "
                    "Expected str, FunctionTool, or MCPServerStreamableHttp."
                )

        self.tools = resolved_tools
        self.mcp_servers = mcp_servers

        self.agent: Agent = Agent(
            name=name,
            instructions=instructions,
            model=model,
            tools=self.tools,
            mcp_servers=self.mcp_servers or None,
        )

    def run(self, input: str) -> List[str] | str:
        return Runner.run_sync(self.agent, input, context=CelestoConfig())

    async def arun(self, input: str) -> List[str] | str:
        return await Runner.run(self.agent, input, context=CelestoConfig())

    def think(self, query: str) -> List[str] | str:
        prompt = render_prompt(
            THINKING_PROMPT,
            query=query,
        )
        result = Runner.run_sync(self.agent, prompt, context=CelestoConfig())
        return result.final_output

    async def chat(
        self,
        input: str,
        stream: bool = False,
        output_format: Literal["json", "python"] = "python",
    ):
        if stream:
            return await self.stream_chat(input, output_format=output_format)
        else:
            return await Runner.run(self.agent, input=input, context=CelestoConfig())

    async def stream_chat(
        self,
        input: str,
        serialize: bool = True,
    ) -> AsyncIterator[Union[str, AgentOutput]]:
        result = Runner.run_streamed(self.agent, input=input, context=CelestoConfig())
        async for agent_output in format_stream_events(
            result.stream_events(),
            allowed_events=["run_item_stream_event"],
        ):
            if serialize:
                yield agent_output.serialize(dump_json=True)
            else:
                yield agent_output

    def serve(
        self,
        host: Literal["0.0.0.0", "127.0.0.1", "localhost"] = "0.0.0.0",
        port: int = 8000,
        log_level: Literal["debug", "info", "warning", "error"] = "info",
        access_log: bool = True,
    ):
        if host not in ("0.0.0.0", "127.0.0.1", "localhost"):
            raise ValueError(
                f"Invalid host: {host}. Must be 0.0.0.0, 127.0.0.1, or localhost."
            )

        app = self._create_app(host, port)
        print(f"Running Agentor at http://{host}:{port}")
        print(
            f"Agent card available at http://{host}:{port}/.well-known/agent-card.json"
        )
        uvicorn.run(
            app, host=host, port=port, log_level=log_level, access_log=access_log
        )

    def _create_app(self, host: str, port: int) -> FastAPI:
        skills = (
            [
                AgentSkill(
                    id=f"tool_{tool.name.lower().replace(' ', '_')}",
                    name=tool.name,
                    description=tool.description,
                    tags=[],
                )
                for tool in self.tools
            ]
            if self.tools
            else []
        )
        controller = A2AController(
            name=self.name,
            description=self.instructions,
            skills=skills,
            url=f"http://{host}:{port}",
        )
        controller.add_api_route("/chat", self._chat_handler, methods=["POST"])
        controller.add_api_route("/health", self._health_check_handler, methods=["GET"])

        self._register_a2a_handlers(controller)

        app = FastAPI()
        app.include_router(controller)
        return app

    async def _chat_handler(self, data: APIInputRequest) -> str:
        if data.stream:
            return StreamingResponse(
                self.stream_chat(data.input, serialize=True),
                media_type="text/event-stream",
            )
        else:
            result = await self.chat(data.input)
            return result.final_output

    async def _health_check_handler(self) -> Response:
        return Response(status_code=200, content="OK")

    def _register_a2a_handlers(self, controller: A2AController):
        controller.add_handler("message/stream", self._message_stream_handler)

    async def _message_stream_handler(
        self, request: a2a_types.SendStreamingMessageRequest
    ) -> StreamingResponse:
        async def event_generator() -> AsyncGenerator[str, None]:
            task_id = f"task_{uuid.uuid4()}"
            context_id = f"ctx_{uuid.uuid4()}"
            artifact_id = f"artifact_{uuid.uuid4()}"

            try:
                # Send initial task
                task = Task(
                    id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.working),
                )
                response = JSONRPCResponse(id=request.id, result=task.model_dump())
                yield f"data: {json.dumps(response.model_dump())}\n\n"

                # Extract message text
                if (
                    request.params.message.parts is None
                    or len(request.params.message.parts) == 0
                ):
                    raise ValueError(
                        f"Message parts are required but got {request.params.message.parts}."
                    )
                part = request.params.message.parts[0].root
                if part.kind != "text":
                    raise ValueError(f"Invalid part kind: {part.kind}. Must be 'text'.")
                input_text = part.text

                # Stream artifact updates
                result = self.stream_chat(input_text, serialize=False)
                is_first_chunk = True

                async for event in result:
                    event: AgentOutput
                    if event.message is not None:
                        artifact = a2a_types.Artifact(
                            artifact_id=artifact_id,
                            name="response",
                            description="Agent response text",
                            parts=[
                                a2a_types.Part(
                                    root=a2a_types.TextPart(text=event.message)
                                )
                            ],
                        )
                        artifact_update = a2a_types.TaskArtifactUpdateEvent(
                            kind="artifact-update",
                            task_id=task_id,
                            context_id=context_id,
                            artifact=artifact,
                            append=not is_first_chunk,
                        )
                        response = JSONRPCResponse(
                            id=request.id, result=artifact_update.model_dump()
                        )
                        yield f"data: {json.dumps(response.model_dump())}\n\n"
                        is_first_chunk = False

                # Send completion status
                final_status = a2a_types.TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.completed),
                    final=True,
                )
                response = JSONRPCResponse(
                    id=request.id, result=final_status.model_dump()
                )
                yield f"data: {json.dumps(response.model_dump())}\n\n"

            except Exception as e:
                logger.exception(f"Error in A2A stream handler: {e}")

                error_status = a2a_types.TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.failed, message=str(e)),
                    final=True,
                )
                response = JSONRPCResponse(
                    id=request.id, result=error_status.model_dump()
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

    def close(self):
        """Clean up references held by the Agent wrapper."""
        self.agent = None


class CelestoMCPHub:
    def __init__(
        self,
        timeout: int = 10,
        max_retry_attempts: int = 3,
        cache_tools_list: bool = True,
        api_key: Optional[str] = None,
    ) -> None:
        api_key = api_key or CELESTO_API_KEY
        if api_key is None:
            raise ValueError("API key is required to use the Celesto MCP Hub.")
        self.mcp_server = MCPServerStreamableHttp(
            name="Celesto AI MCP Server",
            params={
                "url": f"{CELESTO_BASE_URL}/mcp",
                "headers": {"Authorization": f"Bearer {api_key}"},
                "timeout": timeout,
                "cache_tools_list": cache_tools_list,
                "max_retry_attempts": max_retry_attempts,
            },
        )

    async def __aenter__(self) -> MCPServerStreamableHttp:
        await self.mcp_server.connect()
        return self.mcp_server

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.mcp_server.cleanup()
