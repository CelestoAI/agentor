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
from typing import Any, AsyncIterator, Dict, List, Optional, Union

from agentor.engine.events import Event, RunResult, Usage
from agentor.engine.models import Model, ModelResponse, ToolCall, resolve_model
from agentor.engine.tools import Tool, resolve_tools

logger = logging.getLogger(__name__)

MessageInput = Union[str, List[Dict[str, Any]]]


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
        **model_params: Any,
    ):
        self.name = name
        self.instructions = instructions
        self.context = context
        self.max_turns = max_turns
        self.max_tool_failures = max_tool_failures
        self.tracer = tracer
        self.model: Model = resolve_model(
            model, api_key=api_key, base_url=base_url, **model_params
        )
        self.tools: Dict[str, Tool] = {t.name: t for t in resolve_tools(tools)}

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
        messages: List[Dict[str, Any]] = []
        if self.instructions:
            messages.append({"role": "system", "content": self.instructions})
        if isinstance(input, str):
            messages.append({"role": "user", "content": input})
        else:
            messages.extend(input)
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

    def _schemas(self, disabled: set[str]) -> Optional[List[Dict[str, Any]]]:
        schemas = [
            t.to_openai() for name, t in self.tools.items() if name not in disabled
        ]
        return schemas or None

    # ------------------------------------------------------------ execution

    async def _run_tool(
        self, call: ToolCall, disabled: set[str] = frozenset()
    ) -> Event:
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

        tool = self.tools.get(call.name)
        if tool is None:
            known = ", ".join(sorted(self.tools)) or "none"
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

    async def astream(
        self, input: MessageInput, stream_text: bool = False
    ) -> AsyncIterator[Event]:
        """Run the agent, emitting every event, and trace it if configured.

        Note that a consumer which abandons this generator early stops the
        trace from being exported; `arun` always drains it.
        """
        if self.tracer is None:
            async for event in self._astream(input, stream_text):
                yield event
            return

        collector = self.tracer.collector(self.name)
        async for event in self._astream(input, stream_text):
            try:
                collector.handle(event)
            except Exception as e:  # tracing must never break a run
                logger.warning("Trace collection failed: %s", e)
            yield event

        try:
            await asyncio.to_thread(self.tracer.export, collector)
        except Exception as e:
            logger.warning("Trace export failed: %s", e)

    async def _astream(
        self, input: MessageInput, stream_text: bool = False
    ) -> AsyncIterator[Event]:
        messages = self._initial_messages(input)
        failures: Dict[str, int] = {}
        disabled: set[str] = set()
        total = Usage()

        model_name = getattr(self.model, "model", None)
        run_started = time.time()

        yield Event(
            type="run_start",
            agent=self.name,
            model=model_name,
            started_at=run_started,
        )

        for turn in range(1, self.max_turns + 1):
            schemas = self._schemas(disabled)
            # snapshot before the call: `messages` is appended to below, and a
            # trace needs the request as it was actually sent
            request_messages = [dict(m) for m in messages]
            call_started = time.time()

            if stream_text:
                response = None
                async for chunk in self.model.stream(messages, schemas):
                    if chunk.delta:
                        yield Event(type="text_delta", text=chunk.delta, turn=turn)
                    if chunk.final is not None:
                        response = chunk.final
                if response is None:
                    response = ModelResponse()
            else:
                response = await self.model.complete(messages, schemas)

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
                *(self._run_tool(call, disabled) for call in response.tool_calls)
            )

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
                    or event.name not in self.tools
                    or event.name in disabled
                ):
                    continue

                failures[event.name] = failures.get(event.name, 0) + 1
                if failures[event.name] >= self.max_tool_failures:
                    # Retrying a tool that keeps failing just burns turns. Drop
                    # it and let the model finish with what is left.
                    disabled.add(event.name)
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"The tool '{event.name}' failed "
                                f"{failures[event.name]} times and is now "
                                "unavailable. Answer without it, or explain "
                                "what you cannot do."
                            ),
                        }
                    )

        yield Event(
            type="run_end",
            status="max_turns",
            error=f"Reached max_turns ({self.max_turns}) without a final answer.",
            usage=total,
            started_at=run_started,
            ended_at=time.time(),
        )

    async def arun(self, input: MessageInput) -> RunResult:
        result = RunResult()
        async for event in self.astream(input):
            result.events.append(event)
            if event.type == "run_end":
                result.status = event.status or "completed"
                result.final_output = event.text
                result.usage = event.usage or Usage()
                result.error = event.error
        return result

    def run(self, input: MessageInput) -> RunResult:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.arun(input))
        raise RuntimeError(
            "run() cannot be called from a running event loop; await arun() instead."
        )
