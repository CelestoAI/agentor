"""The agent loop.

Call the model; if it asked for tools, run them and feed the results back;
repeat until it stops asking or a budget is hit. Everything the engine does
is emitted as an `Event`, and `arun`/`run` are projections of `astream`.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from agentor.engine.events import Event, RunResult, Usage
from agentor.engine.models import Model, ModelResponse, ToolCall, resolve_model
from agentor.engine.tools import Tool, resolve_tools

logger = logging.getLogger(__name__)

MessageInput = Union[str, List[Dict[str, Any]]]


def _strictify(node: Any) -> Any:
    """Make a JSON schema satisfy OpenAI\'s strict json_schema rules.

    Strict mode requires every object - including nested ones and `$defs` - to
    set `additionalProperties: false` and to list every property in `required`.
    Setting it only on the root gets otherwise valid models rejected before
    generation. Optional fields are already emitted as nullable unions by
    pydantic, so listing them as required is correct.
    """
    if isinstance(node, list):
        return [_strictify(item) for item in node]
    if not isinstance(node, dict):
        return node

    node = {key: _strictify(value) for key, value in node.items()}
    if isinstance(node.get("properties"), dict):
        node["type"] = node.get("type", "object")
        node["additionalProperties"] = False
        node["required"] = list(node["properties"])
    elif node.get("type") == "object" and isinstance(
        node.get("additionalProperties"), dict
    ):
        # An open map (dict[str, X]) has no fixed properties, and strict mode
        # requires every object to enumerate them. No normalisation makes this
        # legal, so fail here rather than on a provider 400 mid-run.
        raise TypeError(
            "output_type contains a dict/mapping field, which OpenAI strict "
            "structured output cannot express. Model the keys explicitly, or "
            "use a list of key/value objects."
        )
    return node


def _clone_server(server: Any) -> Any:
    """Build a fresh, unconnected copy of an MCP server template."""
    clone = object.__new__(type(server))
    clone.__dict__.update(server.__dict__)
    clone._stack = None
    clone._session = None
    clone._loop = None
    return clone


def _response_format(output_type: Any) -> Optional[Dict[str, Any]]:
    """Build an OpenAI json_schema response format from a pydantic model."""
    if output_type is None:
        return None
    if not hasattr(output_type, "model_json_schema"):
        raise TypeError(
            f"output_type must be a pydantic BaseModel, got {output_type!r}."
        )

    schema = _strictify(output_type.model_json_schema())
    return {
        "type": "json_schema",
        "json_schema": {
            "name": output_type.__name__,
            "schema": schema,
            "strict": True,
        },
    }


class AgentLoop:
    """A single agent: a model, some tools, and the loop that drives them."""

    def __init__(
        self,
        name: str = "Agent",
        model: Any = "gpt-4o-mini",
        instructions: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        context: Any = None,
        max_turns: int = 10,
        max_tool_failures: int = 2,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        tracer: Any = None,
        trace_group_id: Optional[str] = None,
        trace_metadata: Optional[Dict[str, Any]] = None,
        store: Any = None,
        mcp_servers: Optional[List[Any]] = None,
        output_type: Any = None,
        **model_params: Any,
    ):
        self.name = name
        self.instructions = instructions
        self.context = context
        self.max_turns = max_turns
        self.max_tool_failures = max_tool_failures
        self.tracer = tracer
        self.trace_group_id = trace_group_id
        self.trace_metadata = trace_metadata
        self.store = store
        self.mcp_servers = list(mcp_servers or [])
        self.output_type = output_type
        self._response_format = _response_format(output_type)
        self.model: Model = resolve_model(
            model, api_key=api_key, base_url=base_url, **model_params
        )
        self.tools: Dict[str, Tool] = {t.name: t for t in resolve_tools(tools)}

    def _tracer_for_run(self, tracing: Any) -> Any:
        """Resolve which tracer, if any, a single run should use.

        `tracing` may also be a tracer object, which is used for that run only
        and never stored: a caller opting one run in must not silently leave
        the agent tracing every run after it.

        Identity comparisons rather than truthiness, since a tracer object is
        itself truthy.
        """
        if tracing is None:
            return self.tracer
        if tracing is False:
            return None
        if tracing is True:
            if self.tracer is None:
                raise ValueError(
                    "tracing=True but no tracer is configured. Pass tracer= "
                    "when building the agent, or set CELESTO_API_KEY."
                )
            return self.tracer
        return tracing

    def with_model(self, model: Any, **kwargs: Any) -> "AgentLoop":
        """Copy this loop with a different model.

        Cheap because the model is a separate object from the agent: tools are
        already resolved and are shared, not rebuilt.
        """
        clone = object.__new__(AgentLoop)
        clone.__dict__.update(self.__dict__)
        clone.model = resolve_model(model, **kwargs)
        return clone

    # ------------------------------------------------------------ messages

    def _initial_messages(self, input: MessageInput) -> List[Dict[str, Any]]:
        if isinstance(input, str):
            messages: List[Dict[str, Any]] = []
            if self.instructions:
                messages.append({"role": "system", "content": self.instructions})
            messages.append({"role": "user", "content": input})
            return messages

        messages = list(input)
        # A replayed run, or a caller supplying their own history, already
        # carries its system message. Prepending another sends the instructions
        # twice, which changes behaviour and some providers reject outright.
        has_system = any(m.get("role") == "system" for m in messages)
        if self.instructions and not has_system:
            messages.insert(0, {"role": "system", "content": self.instructions})
        return messages

    @staticmethod
    def _assistant_message(response: ModelResponse) -> Dict[str, Any]:
        message: Dict[str, Any] = {"role": "assistant", "content": response.content}
        if response.tool_calls:
            message["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in response.tool_calls
            ]
        return message

    @staticmethod
    def _schemas(
        tools: Dict[str, Tool], disabled: set[str]
    ) -> Optional[List[Dict[str, Any]]]:
        schemas = [t.to_openai() for name, t in tools.items() if name not in disabled]
        return schemas or None

    # ------------------------------------------------------------ execution

    async def _run_tool(
        self,
        call: ToolCall,
        tools: Optional[Dict[str, Tool]] = None,
        disabled: set[str] = frozenset(),
    ) -> Event:
        tools = self.tools if tools is None else tools
        try:
            args = json.loads(call.arguments or "{}")
        except json.JSONDecodeError as exc:
            return Event(
                type="tool_result",
                name=call.name,
                call_id=call.id,
                error=f"Invalid JSON arguments: {exc}",
                result=f"Error: arguments were not valid JSON ({exc}).",
            )

        if call.name in disabled:
            # Withdrawing the schema is not enough on its own: a model can still
            # emit a call for a tool it was not offered, which would let a
            # broken tool run past its budget.
            return Event(
                type="tool_result",
                name=call.name,
                args=args,
                call_id=call.id,
                error="tool disabled",
                result=f"Error: tool {call.name!r} is disabled after repeated failures.",
            )

        tool = tools.get(call.name)
        if tool is None:
            known = ", ".join(sorted(tools)) or "none"
            return Event(
                type="tool_result",
                name=call.name,
                args=args,
                call_id=call.id,
                error="unknown tool",
                result=f"Error: unknown tool {call.name!r}. Available tools: {known}.",
            )

        started = time.time()
        try:
            result = await tool.call(args, context=self.context)
            return Event(
                type="tool_result",
                name=call.name,
                args=args,
                call_id=call.id,
                result=result,
                started_at=started,
                ended_at=time.time(),
            )
        except Exception as exc:
            # Surfaced to the model rather than raised: a failing tool is
            # usually recoverable, and the failure budget stops it looping.
            logger.warning("Tool %s failed: %s", call.name, exc, exc_info=True)
            return Event(
                type="tool_result",
                name=call.name,
                args=args,
                call_id=call.id,
                error=f"{type(exc).__name__}: {exc}",
                result=f"Error: {type(exc).__name__}: {exc}",
                started_at=started,
                ended_at=time.time(),
            )

    # ------------------------------------------------------------ the loop

    @asynccontextmanager
    async def _connected_mcp_tools(self):
        """Yield the tool map for one run, with MCP tools merged in.

        The map is built per run and `self.tools` is never mutated: concurrent
        runs on one loop (which `Agentor.arun` does for a batch of prompts)
        would otherwise remove each other\'s remote tools mid-flight.

        A fresh `MCPServer` is built per run for the same reason - the server
        object holds a live session, so sharing one across concurrent runs
        would let the first to finish close a session another is still using.
        """
        if not self.mcp_servers:
            yield dict(self.tools)
            return

        tools = dict(self.tools)
        connected: List[Any] = []
        try:
            for template in self.mcp_servers:
                server = _clone_server(template)
                remote_tools = await server.connect()
                connected.append(server)
                for tool in remote_tools:
                    if tool.name in tools:
                        logger.warning(
                            "MCP server %s exposes %r, which shadows an existing "
                            "tool; use tool_prefix to disambiguate.",
                            server.name,
                            tool.name,
                        )
                        continue
                    tools[tool.name] = tool
            yield tools
        finally:
            for server in connected:
                await server.close()

    async def astream(
        self,
        input: MessageInput,
        stream_text: bool = False,
        run_id: Optional[str] = None,
        max_turns: Optional[int] = None,
        tracing: Any = None,
    ) -> AsyncIterator[Event]:
        """Run the agent, emitting every event, tracing and persisting it.

        `tracing` overrides the configured tracer for this run alone: None uses
        it, False turns it off, True requires one. Useful when a particular
        input must not leave the process.

        Note that a consumer which abandons this generator early stops the
        trace from being exported; `arun` always drains it.
        """
        tracer = self._tracer_for_run(tracing)
        collector = (
            tracer.collector(
                self.name,
                group_id=self.trace_group_id,
                metadata=self.trace_metadata,
            )
            if tracer
            else None
        )
        run_started = time.time()

        async def record(event: Event) -> None:
            if collector is not None:
                try:
                    collector.handle(event)
                except Exception as e:  # tracing must never break a run
                    logger.warning("Trace collection failed: %s", e)
            if self.store is not None and run_id is not None:
                try:
                    # FileStore fsyncs every event. Awaiting it on a worker
                    # keeps ordering while leaving the event loop free for
                    # other runs and streams.
                    await asyncio.to_thread(self.store.append, run_id, event)
                except Exception as e:
                    # Losing durability is bad, but killing a live run over it
                    # is worse; the run is still returned to the caller.
                    logger.error("Failed to persist event for run %s: %s", run_id, e)

        # Emitted before MCP setup: a failure there would otherwise leave a log
        # with no run_start, and so no input to resume from.
        messages = self._initial_messages(input)
        start = Event(
            type="run_start",
            agent=self.name,
            model=getattr(self.model, "model", None),
            started_at=run_started,
            messages=[dict(m) for m in messages],
        )
        await record(start)
        yield start

        try:
            async with self._connected_mcp_tools() as tools:
                async for event in self._astream(
                    messages, stream_text, tools, max_turns
                ):
                    await record(event)
                    yield event
        except Exception as exc:
            # A failed run is exactly the one worth tracing, and a durable log
            # without a terminal event cannot be told apart from a run still in
            # flight. Emit one, then re-raise.
            failure = Event(
                type="run_end",
                status="failed",
                error=f"{type(exc).__name__}: {exc}",
                started_at=run_started,
                ended_at=time.time(),
            )
            await record(failure)
            yield failure
            raise
        finally:
            if collector is not None:
                try:
                    await asyncio.to_thread(tracer.export, collector)
                except Exception as e:
                    logger.warning("Trace export failed: %s", e)

    async def _astream(
        self,
        messages: List[Dict[str, Any]],
        stream_text: bool = False,
        tools: Optional[Dict[str, Tool]] = None,
        max_turns: Optional[int] = None,
    ) -> AsyncIterator[Event]:
        tools = self.tools if tools is None else tools
        turn_budget = self.max_turns if max_turns is None else max_turns
        failures: Dict[str, int] = {}
        disabled: set[str] = set()
        total = Usage()

        model_name = getattr(self.model, "model", None)
        run_started = time.time()

        for turn in range(1, turn_budget + 1):
            schemas = self._schemas(tools, disabled)
            # snapshot before the call: `messages` is appended to below, and a
            # trace needs the request as it was actually sent
            request_messages = [dict(m) for m in messages]
            call_started = time.time()

            if stream_text:
                response = None
                # only passed when set, so a Model adapter that predates
                # structured output keeps working
                extra = (self._response_format,) if self._response_format else ()
                async for chunk in self.model.stream(messages, schemas, *extra):
                    if chunk.delta:
                        yield Event(type="text_delta", text=chunk.delta, turn=turn)
                    if chunk.final is not None:
                        response = chunk.final
                if response is None:
                    response = ModelResponse()
            else:
                extra = (self._response_format,) if self._response_format else ()
                response = await self.model.complete(messages, schemas, *extra)

            total = total + response.usage
            assistant = self._assistant_message(response)
            messages.append(assistant)

            yield Event(
                type="generation",
                turn=turn,
                model=model_name,
                messages=request_messages,
                text=response.content,
                calls=assistant.get("tool_calls"),
                usage=response.usage,
                started_at=call_started,
                ended_at=time.time(),
            )

            if not response.tool_calls:
                text = response.content or ""
                if self.output_type is not None:
                    # validate before declaring success, or the log and the
                    # trace record a completed run the caller saw raise
                    self._parse_output(text)
                yield Event(type="message", text=text, turn=turn, usage=response.usage)
                yield Event(
                    type="run_end",
                    text=text,
                    status="completed",
                    usage=total,
                    turn=turn,
                    started_at=run_started,
                    ended_at=time.time(),
                )
                return

            for call in response.tool_calls:
                try:
                    preview = json.loads(call.arguments or "{}")
                except json.JSONDecodeError:
                    preview = None
                yield Event(
                    type="tool_call",
                    name=call.name,
                    args=preview,
                    call_id=call.id,
                    turn=turn,
                )

            results = await asyncio.gather(
                *(self._run_tool(call, tools, disabled) for call in response.tool_calls)
            )

            newly_disabled: List[str] = []
            for event in results:
                event.turn = turn
                yield event
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": event.call_id,
                        "content": event.result or "",
                    }
                )

                if (
                    event.error is None
                    or event.name not in tools
                    or event.name in disabled
                ):
                    continue

                failures[event.name] = failures.get(event.name, 0) + 1
                if failures[event.name] >= self.max_tool_failures:
                    # Retrying a tool that keeps failing just burns turns. Drop
                    # it and let the model finish with what is left.
                    disabled.add(event.name)
                    newly_disabled.append(event.name)

            # Deferred until every tool result for this turn is in. Appending a
            # notice mid-loop splits the run of `tool` messages answering one
            # assistant turn, and providers reject that outright - so the budget
            # meant to keep a run alive was ending it instead.
            for name in newly_disabled:
                messages.append(
                    {
                        "role": "user",
                        "content": (
                            f"The tool '{name}' failed {failures[name]} times "
                            "and is now unavailable. Answer without it, or "
                            "explain what you cannot do."
                        ),
                    }
                )

        yield Event(
            type="run_end",
            status="max_turns",
            error=f"Reached max_turns ({turn_budget}) without a final answer.",
            usage=total,
            started_at=run_started,
            ended_at=time.time(),
        )

    async def arun(
        self,
        input: MessageInput,
        run_id: Optional[str] = None,
        max_turns: Optional[int] = None,
        tracing: Any = None,
    ) -> RunResult:
        if self.store is not None and run_id is None:
            from agentor.engine.store import new_run_id

            run_id = new_run_id()

        result = RunResult(run_id=run_id)
        async for event in self.astream(
            input, run_id=run_id, max_turns=max_turns, tracing=tracing
        ):
            result.events.append(event)
            if event.type == "run_end":
                result.status = event.status or "completed"
                result.final_output = event.text
                result.usage = event.usage or Usage()
                result.error = event.error

        # documented as "feed this back in to continue the conversation", so it
        # has to actually contain the conversation
        from agentor.engine.store import replay_messages

        result.messages = replay_messages(result.events)

        # Events stay plain text so the log remains JSON-serialisable; only the
        # returned result carries the parsed object.
        if self.output_type is not None and result.status == "completed":
            result.final_output = self._parse_output(result.final_output)
        return result

    def _parse_output(self, text: Optional[str]) -> Any:
        if not text:
            return None
        try:
            return self.output_type.model_validate_json(text)
        except Exception as e:
            raise ValueError(
                f"Model output did not match {self.output_type.__name__}: {e}\n"
                f"Raw output: {text[:500]}"
            ) from e

    def run(
        self,
        input: MessageInput,
        run_id: Optional[str] = None,
        max_turns: Optional[int] = None,
        tracing: Any = None,
    ) -> RunResult:
        return self._sync(
            self.arun(input, run_id=run_id, max_turns=max_turns, tracing=tracing)
        )

    async def aresume(self, run_id: str) -> RunResult:
        """Continue a persisted run from where it stopped.

        A completed run is returned as-is rather than re-executed, so calling
        this after a crash is safe whether or not the run had finished.

        Not safe against concurrent resumes of the *same unfinished* run: two
        callers can both see it as incomplete and continue it, re-running
        side-effecting tools. The bundled stores are single-process and carry
        no lease or lock; coordinate externally if several workers can recover
        the same run.
        """
        if self.store is None:
            raise ValueError("resume() requires a store; pass store= to AgentLoop.")

        from agentor.engine.store import (
            final_event,
            is_complete,
            replay_messages,
            total_usage,
        )

        events = self.store.load(run_id)
        if not events:
            raise KeyError(f"No persisted run with id {run_id!r}.")

        if is_complete(events):
            end = final_event(events)
            output = end.text if end else None
            if self.output_type is not None:
                # otherwise resume() returns a str for a finished run and a
                # parsed model for one it had to continue
                output = self._parse_output(output)
            return RunResult(
                run_id=run_id,
                final_output=output,
                status="completed",
                events=events,
                usage=total_usage(events),
            )

        messages = replay_messages(events)
        if not messages:
            raise ValueError(
                f"Run {run_id!r} has no recoverable messages; start a new run."
            )

        result = await self.arun(messages, run_id=run_id)
        # the caller cares about the whole run, not just this continuation
        result.events = events + result.events
        # ...including what it cost. The continuation's run_end only counts its
        # own generations, so billing a resumed run from it hides everything
        # spent before the interruption.
        result.usage = total_usage(result.events)
        return result

    def resume(self, run_id: str) -> RunResult:
        return self._sync(self.aresume(run_id))

    @staticmethod
    def _sync(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        coro.close()
        raise RuntimeError(
            "This method cannot be called from a running event loop; "
            "await the async variant instead."
        )
