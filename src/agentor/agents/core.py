from datetime import datetime
import json
import os
from a2a.types import JSONRPCResponse, Message, Part, Task, TaskState, TaskStatus
from fastapi.responses import Response, StreamingResponse
import uvicorn
from typing import (
    AsyncGenerator,
    AsyncIterator,
    List,
    Literal,
    Optional,
    Union,
)

from fastapi import FastAPI

from agentor.agents.a2a import A2AController, AgentSkill
from agentor.tools.registry import CelestoConfig, ToolRegistry
from agents import Agent, FunctionTool, Runner, function_tool
from agentor.prompts import THINKING_PROMPT, render_prompt

from agentor.output_text_formatter import AgentOutput, format_stream_events
from typing import (
    Any,
    Dict,
    TypedDict,
)
from a2a import types as a2a_types


from pydantic import BaseModel


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


class Agentor:
    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str] = "gpt-5-nano",
        tools: List[Union[FunctionTool, str]] = [],
        debug: bool = False,
    ):
        self.tools: List[FunctionTool] = [
            ToolRegistry.get(tool)["tool"] if isinstance(tool, str) else tool
            for tool in tools
        ]
        self.name = name
        self.instructions = instructions
        self.model = model

        if os.environ.get("OPENAI_API_KEY") is None:
            raise ValueError("""OPENAI_API_KEY is required to use the Agentor.
            Please set the OPENAI_API_KEY environment variable.""")
        self.agent: Agent = Agent(
            name=name, instructions=instructions, model=model, tools=self.tools
        )

    def run(self, input: str) -> List[str] | str:
        return Runner.run_sync(self.agent, input, context=CelestoConfig())

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
            task_id = f"task_{int(datetime.utcnow().timestamp())}"
            context_id = f"ctx_{int(datetime.utcnow().timestamp())}"

            # 1. Send initial task creation
            task = Task(
                id=task_id,
                contextId=context_id,
                status=TaskStatus(state=TaskState.working),
            )
            response = JSONRPCResponse(id=request.id, result=task.model_dump())
            yield f"data: {json.dumps(response.model_dump())}\n\n"

            # 2. Send message response
            part = request.params.message.parts[0].root
            if part.kind != "text":
                raise ValueError(f"Invalid part kind: {part.kind}. Must be 'text'.")
            input_text = part.text
            result = self.stream_chat(input_text, serialize=False)
            async for event in result:
                event: AgentOutput
                if event.message is not None:
                    message = Message(
                        messageId=f"msg_{int(datetime.utcnow().timestamp())}",
                        role="agent",
                        parts=[Part(type="text", text=event.message)],
                    )
                    response = JSONRPCResponse(
                        id=request.id, result=message.model_dump()
                    )
                    yield f"data: {json.dumps(response.model_dump())}\n\n"

            # 3. Send final status update
            final_status = a2a_types.TaskStatusUpdateEvent(
                taskId=task_id,
                contextId=context_id,
                status=TaskStatus(state=TaskState.completed),
                final=True,
            )
            response = JSONRPCResponse(id=request.id, result=final_status.model_dump())
            yield f"data: {json.dumps(response.model_dump())}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
