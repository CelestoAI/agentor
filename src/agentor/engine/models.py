"""Model adapters.

Only one shape is needed to reach almost every provider: an OpenAI-compatible
`/chat/completions` endpoint. Anthropic, Gemini, Groq, Together, OpenRouter,
Fireworks, DeepSeek, xAI, Mistral, vLLM and Ollama all expose one, so pointing
`base_url` at them is enough. litellm stays available for the long tail.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol, runtime_checkable

from agentor.engine.events import Usage


@dataclass
class ToolCall:
    id: str
    name: str
    #: raw JSON string, exactly as the model emitted it
    arguments: str = ""


@dataclass
class ModelResponse:
    content: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    #: provider payload, for tracing
    raw: Any = None
    #: the model's reasoning/thinking text, when the provider returns it;
    #: declared last so the positional order of the released fields
    #: (content, tool_calls, usage, raw) stays what it always was
    reasoning: Optional[str] = None


@dataclass
class StreamChunk:
    """One streamed step. `final` is set only on the last chunk."""

    delta: Optional[str] = None
    final: Optional[ModelResponse] = None


@runtime_checkable
class Model(Protocol):
    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse: ...

    def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[StreamChunk]: ...


def _reasoning(message: Any) -> Optional[str]:
    """Read the reasoning text off a message or streamed delta.

    Not part of the OpenAI spec, so the field name varies by provider:
    `reasoning_content` (DeepSeek, vLLM, and most compatible servers) or
    `reasoning` (OpenRouter). Absent on true OpenAI responses.
    """
    for attr in ("reasoning_content", "reasoning"):
        value = getattr(message, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _usage(raw: Any) -> Usage:
    usage = getattr(raw, "usage", None)
    if usage is None:
        return Usage()
    return Usage(
        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        total_tokens=getattr(usage, "total_tokens", 0) or 0,
    )


class ChatCompletionsModel:
    """Any OpenAI-compatible chat-completions endpoint."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        client: Any = None,
        **params: Any,
    ):
        self.model = model
        self.params = params

        if client is not None:
            self.client = client
        else:
            from openai import AsyncOpenAI

            self.client = AsyncOpenAI(
                api_key=api_key or os.environ.get("OPENAI_API_KEY"),
                base_url=base_url,
            )

    def _request(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]],
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            **self.params,
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format
        return payload

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse:
        raw = await self.client.chat.completions.create(
            **self._request(messages, tools, response_format)
        )
        message = raw.choices[0].message
        return ModelResponse(
            content=message.content,
            tool_calls=[
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments or "",
                )
                for tc in (message.tool_calls or [])
            ],
            usage=_usage(raw),
            reasoning=_reasoning(message),
            raw=raw,
        )

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[StreamChunk]:
        request = self._request(messages, tools, response_format)
        request["stream"] = True
        request["stream_options"] = {"include_usage": True}

        content: List[str] = []
        reasoning: List[str] = []
        # Tool calls arrive fragmented and out of order; `index` is the only
        # reliable key, and id/name may appear in a later chunk than the first
        # for that index.
        partial: Dict[int, Dict[str, str]] = {}
        usage = Usage()

        try:
            stream = await self.client.chat.completions.create(**request)
        except TypeError:
            # Some OpenAI-compatible servers reject stream_options.
            request.pop("stream_options", None)
            stream = await self.client.chat.completions.create(**request)

        async for event in stream:
            if getattr(event, "usage", None):
                usage = _usage(event)
            if not event.choices:
                continue

            delta = event.choices[0].delta
            if delta is None:
                continue

            if delta.content:
                content.append(delta.content)
                yield StreamChunk(delta=delta.content)

            # accumulated but not yielded as deltas: StreamChunk carries answer
            # text, and reasoning belongs to the trace via the final response
            chunk_reasoning = _reasoning(delta)
            if chunk_reasoning:
                reasoning.append(chunk_reasoning)

            for tc in delta.tool_calls or []:
                slot = partial.setdefault(
                    tc.index, {"id": "", "name": "", "arguments": ""}
                )
                if tc.id:
                    slot["id"] = tc.id
                if tc.function and tc.function.name:
                    slot["name"] = tc.function.name
                if tc.function and tc.function.arguments:
                    slot["arguments"] += tc.function.arguments

        yield StreamChunk(
            final=ModelResponse(
                content="".join(content) or None,
                tool_calls=[
                    ToolCall(id=s["id"], name=s["name"], arguments=s["arguments"])
                    for _, s in sorted(partial.items())
                ],
                usage=usage,
                reasoning="".join(reasoning) or None,
            )
        )


class LiteLLMModel:
    """Escape hatch for providers with no OpenAI-compatible endpoint.

    Kept behind a lazy import so it costs nothing unless used.
    """

    def __init__(self, model: str, api_key: Optional[str] = None, **params: Any):
        self.model = model
        self.api_key = api_key
        self.params = params

    async def complete(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> ModelResponse:
        import litellm

        raw = await litellm.acompletion(
            model=self.model,
            messages=messages,
            tools=tools or None,
            api_key=self.api_key,
            response_format=response_format,
            **self.params,
        )
        message = raw.choices[0].message
        return ModelResponse(
            content=message.content,
            tool_calls=[
                ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=tc.function.arguments or "",
                )
                for tc in (getattr(message, "tool_calls", None) or [])
            ],
            usage=_usage(raw),
            reasoning=_reasoning(message),
            raw=raw,
        )

    async def stream(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict]] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> AsyncIterator[StreamChunk]:
        # litellm mirrors the OpenAI streaming shape, so reuse that accumulator
        # rather than maintaining a second one.
        import litellm

        model = ChatCompletionsModel.__new__(ChatCompletionsModel)
        model.model = self.model
        model.params = self.params

        class _Shim:
            class chat:
                class completions:
                    @staticmethod
                    async def create(**kwargs):
                        kwargs.pop("stream_options", None)
                        return await litellm.acompletion(api_key=self.api_key, **kwargs)

        model.client = _Shim()
        async for chunk in model.stream(messages, tools, response_format):
            yield chunk


def resolve_model(
    model: Any,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    **params: Any,
) -> Model:
    """Turn a user-supplied model into a `Model`.

    A `provider/name` string routes to litellm, matching what the openai-agents
    engine does today, so existing model strings keep working.
    """
    if isinstance(model, str):
        if "/" in model and base_url is None:
            return LiteLLMModel(model, api_key=api_key, **params)
        return ChatCompletionsModel(model, api_key=api_key, base_url=base_url, **params)
    return model
