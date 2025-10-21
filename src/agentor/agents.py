import sys
import json
import traceback
from typing import (
    Any,
    Dict,
    List,
    Literal,
    Optional,
    TypedDict,
    Union,
)


from litestar.exceptions import HTTPException
from litestar.openapi.plugins import SwaggerRenderPlugin
from litestar.openapi.config import OpenAPIConfig
from litestar import Litestar, Request, get, post, Response

from agentor.tools.registry import ToolRegistry
from agents import Agent, FunctionTool, Runner, function_tool
from agentor.prompts import THINKING_PROMPT, render_prompt
from agentor.type_helper import to_jsonable
from agentor.tools.registry import CelestoConfig


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


class AgentServer:
    def __init__(self, debug: bool = False) -> None:
        @post("/chat")
        async def _chat_handler(data: APIInputRequest) -> str:
            result = await self.chat(data.input)
            return result.final_output

        @get("/health")
        def health_handler() -> Response:
            return Response(status_code=200, content="OK")

        self._app = Litestar(
            [_chat_handler, health_handler],
            openapi_config=OpenAPIConfig(
                title="Agentor",
                description="Agentor is a tool for building and deploying AI Agents.",
                version="0.1.0",
                path="/",
            ),
            plugins=[SwaggerRenderPlugin()],
            debug=debug,
            exception_handlers={
                Exception: self._exception_handler,
                HTTPException: self._http_exception_handler,
            },
        )

    @staticmethod
    def _exception_handler(request: Request, exc: Exception) -> Response:
        """Custom exception handler that prints full traceback."""
        print("\n" + "=" * 80)
        print("EXCEPTION CAUGHT:")
        print("=" * 80)
        traceback.print_exc(file=sys.stdout)
        print("=" * 80 + "\n")
        return Response(
            status_code=500,
            content=json.dumps(
                {
                    "error": str(exc),
                    "type": type(exc).__name__,
                    "detail": "Internal server error",
                }
            ),
        )

    @staticmethod
    def _http_exception_handler(request: Request, exc: HTTPException) -> Response:
        """Handler for HTTP exceptions."""
        print(f"\nHTTP Exception: {exc.status_code} - {exc.detail}\n")
        return Response(
            status_code=exc.status_code,
            content=json.dumps({"error": exc.detail, "status_code": exc.status_code}),
        )

    def serve(self, port: int = 8000):
        import uvicorn

        uvicorn.run(
            self._app, host="0.0.0.0", port=port, log_level="debug", access_log=True
        )


class Agentor(AgentServer):
    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str] = "gpt-5-nano",
        tools: List[Union[FunctionTool, str]] = [],
        debug: bool = False,
    ):
        super().__init__(debug=debug)
        tools = [
            ToolRegistry.get(tool)["tool"] if isinstance(tool, str) else tool
            for tool in tools
        ]
        self.name = name
        self.instructions = instructions
        self.model = model
        self.agent: Agent = Agent(
            name=name, instructions=instructions, model=model, tools=tools
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
        output_format: Literal["json", "python"] = "python",
    ):
        result = Runner.run_streamed(self.agent, input=input, context=CelestoConfig())

        async for event in result.stream_events():
            if output_format == "python":
                yield event
                continue

            if event.type == "agent_updated_stream_event":
                yield {"type": "agent_updated", "name": event.new_agent.name}
            elif event.type == "raw_response_event":
                yield {"type": "raw_response", "data": to_jsonable(event.data)}
            elif event.type == "run_item_stream_event":
                yield {"type": "run_item", "item": to_jsonable(event.item)}
            elif event.type == "error":
                yield {"type": "error", "error": to_jsonable(event.error)}
            else:
                yield {"type": "unknown", "event": to_jsonable(event)}
