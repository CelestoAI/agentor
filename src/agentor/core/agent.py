import asyncio
import dataclasses
import json
import logging
import uuid
from pathlib import Path
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

import frontmatter
import litellm
import openai
import uvicorn
from a2a import types as a2a_types
from a2a.types import JSONRPCResponse, Task, TaskState, TaskStatus
from agents import (
    Agent,
    AgentOutputSchemaBase,
    FunctionTool,
    ModelSettings,
    Runner,
    WebSearchTool,
    function_tool,
    set_default_openai_key,
)
from agents.extensions.models.litellm_model import LitellmModel
from agents.mcp import MCPServerStreamableHttp
from agents.models.default_models import get_default_model_settings
from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from agentor.a2a import A2AController, AgentSkill
from agentor.config import celesto_config
from agentor.output_text_formatter import AgentOutput, format_stream_events
from agentor.prompts import THINKING_PROMPT, render_prompt
from agentor.skills import Skills
from agentor.tools.base import BaseTool
from agentor.tools.registry import CelestoConfig, ToolRegistry
from agentor.tracer import setup_celesto_tracing

logger = logging.getLogger(__name__)


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


class AgentInputType(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


class AgentorBase:
    def __init__(
        self,
        name: str,
        instructions: Optional[str],
        model: Optional[str],
        api_key: Optional[str],
        enable_tracing: bool = False,
    ):
        self.agent = None
        self.name = name
        self.instructions = instructions
        self.model = model

        self.api_key = api_key
        if isinstance(model, str) and "/" in model:
            self.model = LitellmModel(model, api_key=api_key)

        self.enable_tracing = enable_tracing
        if self.enable_tracing:
            if not celesto_config.api_key:
                raise ValueError(
                    (
                        "Celesto API key is required to enable tracing.\n",
                        "Find the API key in the dashboard: https://celesto.ai/dashboard \n",
                        "and set it in the environment variable CELESTO_API_KEY.",
                    )
                )
            setup_celesto_tracing(
                endpoint=f"{celesto_config.base_url}/traces/ingest",
                token=celesto_config.api_key.get_secret_value(),
            )
        elif (
            celesto_config.api_key is not None
            and not celesto_config.disable_auto_tracing
        ):
            try:
                print(
                    (
                        "auto enabled LLM monitoring and tracing. View traces: https://celesto.ai/observe"
                        "\nTo disable, set CELESTO_DISABLE_AUTO_TRACING=True."
                    )
                )
                setup_celesto_tracing(
                    endpoint=f"{celesto_config.base_url}/traces/ingest",
                    token=celesto_config.api_key.get_secret_value(),
                )
            except Exception as e:
                logger.warning(f"Failed to setup Celesto tracing: {e}")


class Agentor(AgentorBase):
    """
    Build an Agent, connect tools, and serve as an API in just few lines of code.

    Example:
        >>> from agentor import Agentor
        >>> agent = Agentor(name="Assistant", instructions="You are a helpful assistant")
        >>> result = agent.run("Write a haiku about recursion in programming.")
        >>> print(result)

        >>> # Serve the Agent as an API
        >>> agent.serve(port=8000)

    Use any model supported by LiteLLM, e.g. "gemini/gemini-pro" or "anthropic/claude-4".
        >>> agent = Agentor(name="Assistant", model="gemini/gemini-pro", api_key=os.environ.get("GEMINI_API_KEY"))

    Set model settings to configure the model behavior, e.g. temperature, top_p, etc.
        >>> from agentor import ModelSettings
        >>> model_settings = ModelSettings(temperature=0.5)
        >>> agent = Agentor(name="Assistant", model="gemini/gemini-pro", api_key=os.environ.get("GEMINI_API_KEY"), model_settings=model_settings)
    """

    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Optional[str | LitellmModel] = "gpt-5-nano",
        tools: Optional[
            List[
                Union[
                    FunctionTool,
                    str,
                    MCPServerStreamableHttp,
                    BaseTool,
                ]
            ]
        ] = None,
        output_type: type[Any] | AgentOutputSchemaBase | None = None,
        debug: bool = False,
        api_key: Optional[str] = None,
        model_settings: Optional[ModelSettings] = None,
        skills: Optional[List[str]] = None,
        enable_tracing: bool = False,
    ):
        if skills is not None:
            available_skills = self._inject_skills(skills)
            instructions = f"{instructions or ''}\n\n{available_skills}"
        super().__init__(name, instructions, model, api_key, enable_tracing)
        tools = tools or []
        resolved_tools: List[FunctionTool] = []
        mcp_servers: List[MCPServerStreamableHttp] = []

        for tool in tools:
            if isinstance(tool, str):
                resolved_tools.append(ToolRegistry.get(tool)["tool"])
            elif isinstance(tool, FunctionTool):
                resolved_tools.append(tool)
            elif isinstance(tool, BaseTool):
                # Convert all capabilities to individual OpenAI functions
                resolved_tools.extend(tool.to_openai_function())
            elif isinstance(tool, MCPServerStreamableHttp):
                mcp_servers.append(tool)
            elif isinstance(tool, WebSearchTool):
                resolved_tools.append(tool)
            else:
                raise TypeError(
                    f"Unsupported tool type '{type(tool).__name__}'. "
                    "Expected str, FunctionTool, ToolConvertor, BaseTool, or MCPServerStreamableHttp."
                )

        self.tools = resolved_tools
        self.mcp_servers = mcp_servers

        if model_settings is None:
            model_settings = get_default_model_settings()

        if self.api_key:
            set_default_openai_key(self.api_key)

        self.agent: Agent = Agent(
            name=name,
            instructions=instructions,
            model=self.model,
            tools=self.tools,
            mcp_servers=self.mcp_servers or [],
            output_type=output_type,
            model_settings=model_settings,
        )

    def _inject_skills(self, skills: List[str]) -> str:
        """Inject skills into the agent system prompt."""
        instructions = []
        for skill in skills:
            skill = Skills.load_from_path(skill)
            instructions.append(f"{skill.to_xml()}")
        return "<available_skills>" + "".join(instructions) + "</available_skills>"

    @classmethod
    def from_md(
        cls,
        md_path: str | Path,
        *,
        model: Optional[str | LitellmModel] = None,
        tools: Optional[
            List[
                Union[
                    FunctionTool,
                    str,
                    MCPServerStreamableHttp,
                    BaseTool,
                ]
            ]
        ] = None,
        output_type: type[Any] | AgentOutputSchemaBase | None = None,
        debug: bool = False,
        api_key: Optional[str] = None,
        model_settings: Optional[ModelSettings] = None,
    ) -> "Agentor":
        """
        Create an Agentor instance from a markdown file.

        Expected markdown structure:

            ---
            name: Agent name
            tools: ["get_weather", "gmail"]  # or as a string: "get_weather, gmail"
            model: gpt-4o
            temperature: 0.3
            ---
            System prompt goes here

        The `tools` field is optional. Unknown tools are ignored for now to
        keep the v0 experience simple.

        Note: If `model_settings` is provided without a temperature, the temperature
        from the markdown frontmatter will be merged into it.
        """
        path = Path(md_path)
        if not path.is_file():
            raise FileNotFoundError(f"Markdown file not found: {path}")

        post = frontmatter.loads(path.read_text(encoding="utf-8"))
        metadata = {key.lower(): value for key, value in (post.metadata or {}).items()}

        name = metadata.get("name")
        if not name:
            raise ValueError("Agent name is required in the markdown frontmatter.")

        instructions = post.content.strip()
        if not instructions:
            raise ValueError("Agent instructions are required in the markdown body.")

        temperature = metadata.get("temperature")
        parsed_temperature: Optional[float] = None
        if temperature is not None:
            try:
                parsed_temperature = float(temperature)
            except (TypeError, ValueError):
                raise ValueError(
                    "Temperature in markdown frontmatter must be a number."
                )

        resolved_tools: Optional[
            List[
                Union[
                    FunctionTool,
                    str,
                    MCPServerStreamableHttp,
                    BaseTool,
                ]
            ]
        ]
        if tools is not None:
            resolved_tools = tools
        else:
            tool_names = metadata.get("tools")
            if tool_names:
                if isinstance(tool_names, str):
                    parsed_tools = [item.strip() for item in tool_names.split(",")]
                elif isinstance(tool_names, (list, tuple)):
                    parsed_tools = [str(item).strip() for item in tool_names]
                else:
                    raise ValueError(
                        "Tools in markdown frontmatter must be a string or a list."
                    )
                available_tools = set(ToolRegistry.list())
                unknown_tools = [
                    tool_name
                    for tool_name in parsed_tools
                    if tool_name and tool_name not in available_tools
                ]
                if unknown_tools:
                    logger.warning(
                        "Ignoring unknown tools in %s: %s",
                        path,
                        ", ".join(unknown_tools),
                    )
                resolved_tools = [
                    tool_name
                    for tool_name in parsed_tools
                    if tool_name and tool_name in available_tools
                ] or None
            else:
                resolved_tools = None

        resolved_model_settings = model_settings
        if parsed_temperature is not None:
            if resolved_model_settings is None:
                resolved_model_settings = ModelSettings(temperature=parsed_temperature)
            elif getattr(resolved_model_settings, "temperature", None) is None:
                # Merge temperature from markdown into provided model_settings
                settings_dict = dataclasses.asdict(resolved_model_settings)
                settings_dict["temperature"] = parsed_temperature
                resolved_model_settings = ModelSettings(**settings_dict)

        metadata_model = metadata.get("model")
        resolved_model = model or metadata_model or "gpt-5-nano"

        return cls(
            name=name,
            instructions=instructions,
            model=resolved_model,
            tools=resolved_tools,
            output_type=output_type,
            debug=debug,
            api_key=api_key,
            model_settings=resolved_model_settings,
        )

    def run(self, input: str) -> List[str] | str:
        return Runner.run_sync(self.agent, input, context=CelestoConfig())

    async def arun(
        self,
        input: list[str] | str | list[AgentInputType],
        limit_concurrency: int = 10,
        max_turns: int = 20,
        fallback_models: Optional[List[str]] = None,
    ) -> List[str] | str:
        """
        Run the agent with an input prompt or a batch of prompts.
        In case of a batch of prompts, the agent will run each prompt concurrently.

        Args:
            input: A string prompt or a list of string prompts.
            limit_concurrency: The maximum number of concurrent tasks to run in case of a batch of prompts.
            max_turns: The maximum number of turns to run the agent.
            fallback_models: Optional list of fallback model names to try if the primary model
                fails due to rate limits or API errors. Models are tried in order.
        """
        if isinstance(input, list):
            if isinstance(input[0], dict):
                return await Runner.run(self.agent, input, context=CelestoConfig())

            futures = []
            if limit_concurrency > 0:
                semaphore = asyncio.Semaphore(limit_concurrency)

                async def _run_task(task: str) -> str:
                    async with semaphore:
                        return await self._run_with_fallback(
                            task, max_turns, fallback_models
                        )

                futures = [_run_task(task) for task in input]
                return await asyncio.gather(*futures, return_exceptions=True)
            else:
                return await asyncio.gather(
                    *[
                        self._run_with_fallback(task, max_turns, fallback_models)
                        for task in input
                    ],
                    return_exceptions=True,
                )
        else:
            return await self._run_with_fallback(input, max_turns, fallback_models)

    async def _run_with_fallback(
        self,
        task: str,
        max_turns: int,
        fallback_models: Optional[List[str]] = None,
    ):
        """
        Run a task with optional fallback to alternative models on rate limit errors.
        """
        try:
            return await Runner.run(
                self.agent,
                task,
                context=CelestoConfig(),
                max_turns=max_turns,
            )
        except (
            openai.RateLimitError,
            litellm.RateLimitError,
            openai.APIError,
            litellm.APIError,
        ) as e:
            if not fallback_models:
                raise

            logger.warning(
                f"Primary model failed with {type(e).__name__}: {e}. "
                f"Trying fallback models: {fallback_models}"
            )

            for fallback_model in fallback_models:
                try:
                    # Create a temporary agent with the fallback model
                    fallback_agent = Agent(
                        name=self.agent.name,
                        instructions=self.agent.instructions,
                        model=LitellmModel(fallback_model)
                        if "/" in fallback_model
                        else fallback_model,
                        tools=self.tools,
                        mcp_servers=self.mcp_servers or [],
                        output_type=self.agent.output_type,
                        model_settings=self.agent.model_settings,
                    )
                    return await Runner.run(
                        fallback_agent,
                        task,
                        context=CelestoConfig(),
                        max_turns=max_turns,
                    )
                except (
                    openai.RateLimitError,
                    litellm.RateLimitError,
                    openai.APIError,
                    litellm.APIError,
                ) as fallback_error:
                    logger.warning(
                        f"Fallback model '{fallback_model}' also failed: {fallback_error}"
                    )
                    continue

            # All fallback models failed, raise the original error
            raise

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
        serialize: bool = True,
    ):
        if stream:
            return self.stream_chat(input, serialize=serialize)
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


class CelestoMCPHub:
    def __init__(
        self,
        timeout: int = 10,
        max_retry_attempts: int = 3,
        cache_tools_list: bool = True,
        api_key: Optional[str] = None,
    ) -> None:
        api_key = api_key or celesto_config.api_key.get_secret_value()
        if api_key is None:
            raise ValueError("API key is required to use the Celesto MCP Hub.")
        self.mcp_server = MCPServerStreamableHttp(
            name="Celesto AI MCP Server",
            params={
                "url": f"{celesto_config.base_url}/mcp",
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
