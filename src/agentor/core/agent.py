from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import sys
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
import openai
from a2a import types as a2a_types
from a2a.types import JSONRPCResponse, Task, TaskState, TaskStatus
from fastapi import FastAPI
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from agentor.a2a import A2AController, AgentSkill
from agentor.config import celesto_config
from agentor.engine import AgentLoop, function_tool
from agentor.engine.mcp import MCPServer
from agentor.engine.settings import ModelSettings
from agentor.engine.tools import resolve_tools
from agentor.output_text_formatter import AgentOutput, ToolAction
from agentor.prompts import THINKING_PROMPT, render_prompt
from agentor.skills import Skills
from agentor.tools.registry import CelestoConfig, ToolRegistry
from agentor.tracer import setup_celesto_tracing

logger = logging.getLogger(__name__)


def _retryable_errors() -> tuple[type[BaseException], ...]:
    """Error types worth retrying on a fallback model.

    litellm's errors are only included when litellm is already loaded, which
    avoids forcing a ~1s import on the OpenAI-only path. Call this when an
    error is in hand, never up front: litellm is imported lazily on its first
    request, so a tuple built before that call would omit its errors and the
    very first rate limit would skip the fallbacks entirely.
    """
    errors: list[type[BaseException]] = [openai.RateLimitError, openai.APIError]
    litellm = sys.modules.get("litellm")
    if litellm is not None:
        errors.extend([litellm.RateLimitError, litellm.APIError])
    return tuple(errors)


def _is_retryable(exc: BaseException) -> bool:
    return isinstance(exc, _retryable_errors())


@function_tool(name_override="get_weather")
def get_dummy_weather(city: str) -> str:
    """Returns the dummy weather in the given city.

    Args:
        city: The city to look up.
    """
    return f"The dummy weather in {city} is sunny"


class APIInputRequest(BaseModel):
    input: Union[str, List[Dict[str, str]]]
    stream: bool = False


class AgentInputType(TypedDict):
    role: Literal["user", "assistant", "system"]
    content: str


class Agentor:
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

    Or point base_url at any OpenAI-compatible endpoint (requires engine="native"):
        >>> agent = Agentor(
        ...     name="Assistant",
        ...     model="openrouter/auto",
        ...     base_url="https://openrouter.ai/api/v1",
        ...     api_key=os.environ["OPENROUTER_API_KEY"],
        ...     engine="native",
        ... )

    Set model settings to configure the model behavior, e.g. temperature, top_p, etc.
        >>> from agentor import ModelSettings
        >>> model_settings = ModelSettings(temperature=0.5)
        >>> agent = Agentor(name="Assistant", model="gemini/gemini-pro", api_key=os.environ.get("GEMINI_API_KEY"), model_settings=model_settings)
    """

    def __init__(
        self,
        name: str,
        instructions: Optional[str] = None,
        model: Any = "gpt-5-nano",
        tools: Optional[List[Any]] = None,
        output_type: Any = None,
        debug: bool = False,
        api_key: Optional[str] = None,
        model_settings: Optional[ModelSettings] = None,
        skills: Optional[List[str]] = None,
        enable_tracing: bool = False,
        max_turns: int = 20,
        store: Any = None,
        base_url: Optional[str] = None,
        tracer: Any = None,
        engine: Optional[Literal["native"]] = None,
    ):
        if engine not in (None, "native"):
            raise ValueError(
                f"Unknown engine {engine!r}. The openai-agents engine was "
                "removed in v0.1.0; the native engine is the only one and is "
                "the default. Drop the engine= argument."
            )
        if skills is not None:
            available_skills = self._inject_skills(skills)
            instructions = f"{instructions or ''}\n\n{available_skills}"

        self._init_native(
            name=name,
            instructions=instructions,
            model=model,
            tools=tools,
            api_key=api_key,
            model_settings=model_settings,
            max_turns=max_turns,
            enable_tracing=enable_tracing,
            store=store,
            output_type=output_type,
            base_url=base_url,
            tracer=tracer,
        )

    def _init_native(
        self,
        name: str,
        instructions: Optional[str],
        model: Any,
        tools: Optional[List[Any]],
        api_key: Optional[str],
        model_settings: Optional[ModelSettings],
        max_turns: int,
        enable_tracing: bool,
        store: Any = None,
        output_type: Any = None,
        base_url: Optional[str] = None,
        tracer: Any = None,
    ) -> None:
        """Set up the native engine (see agentor.engine)."""

        self.name = name
        self.instructions = instructions
        self.api_key = api_key
        self.model = model
        self.enable_tracing = enable_tracing
        # an explicit tracer wins over the one built from CELESTO_API_KEY
        tracer = tracer or self._native_tracer(enable_tracing)

        plain_tools, mcp_servers = [], []
        for tool in tools or []:
            if isinstance(tool, MCPServer):
                mcp_servers.append(tool)
            else:
                plain_tools.append(tool)

        # Fail loudly rather than silently dropping a tool the caller passed.
        self._tools = resolve_tools(plain_tools)
        self.tools = self._tools
        self.mcp_servers = mcp_servers

        params = model_settings.to_params() if model_settings else {}
        self._loop = AgentLoop(
            name=name,
            model=model or "gpt-4o-mini",
            instructions=instructions,
            tools=self._tools,
            context=CelestoConfig(),
            max_turns=max_turns,
            api_key=api_key,
            base_url=base_url,
            tracer=tracer,
            store=store,
            mcp_servers=mcp_servers,
            output_type=output_type,
            **params,
        )

    def _resolve_tracing(self, tracing: Optional[bool]) -> Optional[bool]:
        """Turn a per-run tracing flag into something the loop can act on.

        `tracing=True` on an agent with no tracer is a reasonable request,
        not an error: build one from CELESTO_API_KEY so a single run can be
        traced without turning tracing on for the whole agent.
        """
        if tracing and self._loop.tracer is None:
            if not celesto_config.api_key:
                raise ValueError(
                    "tracing=True requires a Celesto API key. Set "
                    "CELESTO_API_KEY, or pass tracer= when building the agent."
                )
            self._loop.tracer = setup_celesto_tracing(
                endpoint=f"{celesto_config.base_url}/traces/ingest",
                token=celesto_config.api_key.get_secret_value(),
            )
        return tracing

    def _native_tracer(self, enable_tracing: bool):
        """Build a tracer, but only when tracing was asked for.

        Tracing is opt-in. A trace carries prompts, tool arguments and tool
        results, so merely having a Celesto API key configured - which the SDK
        and the MCP hub also use - is not consent to ship run contents to a
        remote endpoint.
        """
        if not enable_tracing:
            return None
        if not celesto_config.api_key:
            raise ValueError(
                "Celesto API key is required to enable tracing. "
                "Find it at https://celesto.ai/dashboard and set CELESTO_API_KEY."
            )

        try:
            return setup_celesto_tracing(
                endpoint=f"{celesto_config.base_url}/traces/ingest",
                token=celesto_config.api_key.get_secret_value(),
            )
        except Exception as e:
            logger.warning(f"Failed to setup Celesto tracing: {e}")
            return None

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
        model: Any = None,
        tools: Optional[List[Any]] = None,
        output_type: Any = None,
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

        resolved_tools: Optional[List[Any]]
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

    def run(self, input: str, tracing: Optional[bool] = None) -> Any:
        """Run the agent.

        Args:
            input: The prompt.
            tracing: Override tracing for this run alone. None keeps whatever
                the agent was configured with, False sends nothing for this
                run, True traces it even when the agent has tracing off.
        """
        return self._loop.run(input, tracing=self._resolve_tracing(tracing))

    async def arun(
        self,
        input: list[str] | str | list[AgentInputType],
        limit_concurrency: int = 10,
        max_turns: Optional[int] = None,
        fallback_models: Optional[List[str]] = None,
        tracing: Optional[bool] = None,
    ) -> List[str] | str:
        """
        Run the agent with an input prompt or a batch of prompts.
        In case of a batch of prompts, the agent will run each prompt concurrently.

        Args:
            input: A string prompt or a list of string prompts.
            limit_concurrency: The maximum number of concurrent tasks to run in case of a batch of prompts.
            max_turns: Maximum turns for this call. Defaults to the value the
                agent was constructed with.
            fallback_models: Optional list of fallback model names to try if the primary model
                fails due to rate limits or API errors. Models are tried in order.
            tracing: Override tracing for this call alone. None keeps the
                agent's configuration, False sends nothing, True traces
                even when the agent has tracing off.
        """
        tracing = self._resolve_tracing(tracing)
        if isinstance(input, list):
            if isinstance(input[0], dict):
                return await self._loop.arun(
                    input, max_turns=max_turns, tracing=tracing
                )

            futures = []
            if limit_concurrency > 0:
                semaphore = asyncio.Semaphore(limit_concurrency)

                async def _run_task(task: str) -> str:
                    async with semaphore:
                        return await self._run_with_fallback(
                            task, max_turns, fallback_models, tracing
                        )

                futures = [_run_task(task) for task in input]
                return await asyncio.gather(*futures, return_exceptions=True)
            else:
                return await asyncio.gather(
                    *[
                        self._run_with_fallback(
                            task, max_turns, fallback_models, tracing
                        )
                        for task in input
                    ],
                    return_exceptions=True,
                )
        else:
            return await self._run_with_fallback(
                input, max_turns, fallback_models, tracing
            )

    async def _run_with_fallback(
        self,
        task: str,
        max_turns: Optional[int] = None,
        fallback_models: Optional[List[str]] = None,
        tracing: Optional[bool] = None,
    ):
        """Run a task, falling back to other models on rate limits.

        Swapping the model copies the loop rather than rebuilding the agent,
        because the model is not baked into the agent here.
        """
        try:
            return await self._loop.arun(task, max_turns=max_turns, tracing=tracing)
        except Exception as e:
            if not _is_retryable(e) or not fallback_models:
                raise
            logger.warning(
                f"Primary model failed with {type(e).__name__}: {e}. "
                f"Trying fallback models: {fallback_models}"
            )
            for fallback_model in fallback_models:
                try:
                    # carry the configured parameters across: a fallback that
                    # silently drops temperature/max_tokens answers differently
                    return await self._loop.with_model(
                        fallback_model,
                        api_key=self.api_key,
                        **getattr(self._loop.model, "params", {}),
                    ).arun(task, max_turns=max_turns, tracing=tracing)
                except Exception as fallback_error:
                    if not _is_retryable(fallback_error):
                        raise
                    logger.warning(
                        f"Fallback model '{fallback_model}' also failed: {fallback_error}"
                    )
                    continue
            raise

    def resume(self, run_id: str):
        """Continue a persisted run. Requires a store."""
        return self._loop.resume(run_id)

    async def aresume(self, run_id: str):
        """Async variant of resume()."""
        return await self._loop.aresume(run_id)

    def think(self, query: str) -> List[str] | str:
        prompt = render_prompt(
            THINKING_PROMPT,
            query=query,
        )
        return self._loop.run(prompt).final_output

    async def chat(
        self,
        input: str,
        stream: bool = False,
        serialize: bool = True,
        tracing: Optional[bool] = None,
    ):
        if stream:
            return self.stream_chat(input, serialize=serialize, tracing=tracing)
        return await self._loop.arun(input, tracing=self._resolve_tracing(tracing))

    async def stream_chat(
        self,
        input: str,
        serialize: bool = True,
        tracing: Optional[bool] = None,
    ) -> AsyncIterator[Union[str, AgentOutput]]:
        async for agent_output in self._native_stream(tracing)(input):
            if serialize:
                yield agent_output.serialize(dump_json=True)
            else:
                yield agent_output

    def _native_stream(self, tracing: Optional[bool] = None):
        """Project engine events onto AgentOutput.

        Keeps `serve()`, the /chat endpoint and the A2A handler working against
        one wire format regardless of which engine produced the run.
        """

        async def stream(input: str) -> AsyncIterator[AgentOutput]:
            # a streamed run is as resumable as a non-streamed one, but only if
            # it is given a run id to persist under
            run_id = None
            if self._loop.store is not None:
                from agentor.engine.store import new_run_id

                run_id = new_run_id()
            async for event in self._loop.astream(
                input, run_id=run_id, tracing=self._resolve_tracing(tracing)
            ):
                if event.type == "message":
                    yield AgentOutput(type="run_item_stream_event", message=event.text)
                elif event.type == "tool_call":
                    yield AgentOutput(
                        type="run_item_stream_event",
                        tool_action=ToolAction(name=event.name, type="tool_called"),
                    )
                elif event.type == "tool_result":
                    yield AgentOutput(
                        type="run_item_stream_event",
                        message=event.result,
                        tool_action=ToolAction(name=event.name, type="tool_output"),
                    )
                elif event.type == "run_end" and event.status != "completed":
                    yield AgentOutput(
                        type="run_item_stream_event",
                        message=event.error or "Run did not complete.",
                    )

        return stream

    def serve(
        self,
        host: Literal["0.0.0.0", "127.0.0.1", "localhost"] = "0.0.0.0",
        port: int = 8000,
        log_level: Literal["debug", "info", "warning", "error"] = "info",
        access_log: bool = True,
    ):
        import uvicorn

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
    """The Celesto-hosted MCP server, as an async context manager."""

    def __init__(
        self,
        timeout: int = 10,
        max_retry_attempts: int = 3,
        cache_tools_list: bool = True,
        api_key: Optional[str] = None,
    ) -> None:
        api_key = api_key or (
            celesto_config.api_key.get_secret_value()
            if celesto_config.api_key
            else None
        )
        if api_key is None:
            raise ValueError("API key is required to use the Celesto MCP Hub.")
        self.mcp_server = MCPServer(
            url=f"{celesto_config.base_url}/mcp",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
            name="Celesto AI MCP Server",
        )

    async def __aenter__(self) -> MCPServer:
        await self.mcp_server.connect()
        return self.mcp_server

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        await self.mcp_server.close()
