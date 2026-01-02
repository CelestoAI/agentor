"""Celesto Trace Exporter for OpenAI Agents SDK.

This module provides a custom trace exporter that sends trace data
to the Celesto backend for storage and visualization.

Usage:
    from celesto_tracer import setup_celesto_tracing

    # Call once at startup
    setup_celesto_tracing(
        endpoint="https://api.celesto.ai/v1/traces/ingest",
        token="your-celesto-api-token",
    )

    # Then run your agents as normal
    from agents import Agent, Runner
    agent = Agent(name="my_agent", ...)
    result = await Runner.run(agent, "Hello!")
"""

import atexit
from typing import Any

import httpx
from agents import RunConfig, add_trace_processor, set_trace_processors
import logging
from agents.tracing import Span, Trace
from agents.tracing.processors import BatchTraceProcessor, TracingExporter


class CelestoExporter(TracingExporter):
    """Exporter that sends trace data to Celesto backend.

    Implements the TracingExporter interface from OpenAI Agents SDK.
    Converts SDK trace/span objects to the Celesto ingest format.
    """

    def __init__(
        self,
        endpoint: str,
        token: str,
        timeout: float = 10.0,
    ):
        """Initialize the Celesto exporter.

        Args:
            endpoint: Celesto ingest API URL (e.g., https://api.celesto.ai/v1/traces/ingest)
            token: Bearer token for authentication
            timeout: HTTP request timeout in seconds
        """
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout
        self._client = httpx.Client(timeout=timeout)

    def export(self, items: list[Trace | Span]) -> None:
        """Export trace/span items to Celesto backend.

        Called by BatchTraceProcessor when batch is ready.
        """
        if not items:
            return

        data = []
        for item in items:
            payload = self._convert_item(item)
            if payload:
                data.append(payload)

        if not data:
            return

        try:
            response = self._client.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={"data": data},
            )
            response.raise_for_status()
        except httpx.HTTPError as e:
            # Log but don't fail the agent run
            print(f"[CelestoExporter] Failed to export traces: {e}")

    def _convert_item(self, item: Trace | Span) -> dict[str, Any] | None:
        """Convert SDK trace/span to Celesto ingest format."""
        # Get the base export data from SDK
        exported = item.export()

        if isinstance(item, Trace):
            return self._convert_trace(item, exported)
        elif isinstance(item, Span):
            return self._convert_span(item, exported)

        return None

    def _convert_trace(self, trace: Trace, exported: dict) -> dict:
        """Convert Trace object to Celesto format."""
        return {
            "object": "trace",
            "id": exported.get("id", trace.trace_id),
            "workflow_name": exported.get("workflow_name")
            or getattr(trace, "name", None),
            "group_id": exported.get("group_id"),
            "metadata": exported.get("metadata"),
        }

    def _convert_span(self, span: Span, exported: dict) -> dict:
        """Convert Span object to Celesto format.

        Enriches the export data with additional fields from the span object.
        """
        payload = {
            "object": "trace.span",
            "span_id": exported.get("span_id", span.span_id),
            "trace_id": exported.get("trace_id", span.trace_id),
            "parent_id": exported.get("parent_id"),
            "started_at": exported.get("started_at"),
            "ended_at": exported.get("ended_at"),
        }

        # Build span_data from exported data and live span object
        span_data = exported.get("span_data", {})

        # Enrich with data from the live span object if available
        if hasattr(span, "span_data") and span.span_data is not None:
            live_data = span.span_data

            # Get type
            if hasattr(live_data, "type"):
                span_data["type"] = live_data.type

            # For response spans, extract rich data
            if hasattr(live_data, "response") and live_data.response is not None:
                resp = live_data.response
                if hasattr(resp, "model_dump"):
                    span_data["response"] = resp.model_dump()
                elif hasattr(resp, "dict"):
                    span_data["response"] = resp.dict()

            # Get input messages
            if hasattr(live_data, "input") and live_data.input is not None:
                span_data["input"] = self._serialize(live_data.input)

            # Get model info
            if hasattr(live_data, "model"):
                span_data["model"] = live_data.model

            # Get usage/tokens
            if hasattr(live_data, "usage") and live_data.usage is not None:
                usage = live_data.usage
                if hasattr(usage, "model_dump"):
                    span_data["usage"] = usage.model_dump()
                elif isinstance(usage, dict):
                    span_data["usage"] = usage

            # For function spans
            if hasattr(live_data, "name"):
                span_data["name"] = live_data.name
            if hasattr(live_data, "output") and live_data.output is not None:
                span_data["output"] = self._serialize(live_data.output)

            # For agent spans
            if hasattr(live_data, "tools"):
                span_data["tools"] = self._serialize(live_data.tools)
            if hasattr(live_data, "handoffs"):
                span_data["handoffs"] = self._serialize(live_data.handoffs)

        payload["span_data"] = span_data

        # Include error if present
        if exported.get("error"):
            payload["error"] = exported["error"]

        return payload

    def _serialize(self, obj: Any) -> Any:
        """Safely serialize an object to JSON-compatible format."""
        if obj is None:
            return None
        if isinstance(obj, (str, int, float, bool)):
            return obj
        if isinstance(obj, (list, tuple)):
            return [self._serialize(item) for item in obj]
        if isinstance(obj, dict):
            return {k: self._serialize(v) for k, v in obj.items()}
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__dict__"):
            return {
                k: self._serialize(v)
                for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
        return str(obj)

    def shutdown(self) -> None:
        """Clean up resources."""
        self._client.close()


# Global processor reference for cleanup
_processor: BatchTraceProcessor | None = None


def setup_celesto_tracing(
    endpoint: str,
    token: str,
    *,
    replace_default: bool = True,
    batch_delay: float = 1.0,
    max_batch_size: int = 256,
) -> BatchTraceProcessor:
    """Set up Celesto tracing for OpenAI Agents SDK.

    Call this once at application startup before running any agents.

    Args:
        endpoint: Celesto ingest API URL
        token: Bearer token for authentication
        replace_default: If True, replace OpenAI's default tracing.
                        If False, add Celesto alongside OpenAI tracing.
        batch_delay: Seconds to wait before flushing a batch
        max_batch_size: Maximum items per batch

    Returns:
        The BatchTraceProcessor (useful for manual flush/shutdown)

    Example:
        >>> processor = setup_celesto_tracing(
        ...     endpoint="https://api.celesto.ai/v1/traces/ingest",
        ...     token="cel_abc123...",
        ... )
        >>> # Run your agents...
        >>> # On shutdown:
        >>> processor.force_flush()
        >>> processor.shutdown()
    """
    global _processor

    exporter = CelestoExporter(endpoint=endpoint, token=token)
    processor = BatchTraceProcessor(
        exporter=exporter,
        schedule_delay=batch_delay,
        max_batch_size=max_batch_size,
    )

    if replace_default:
        set_trace_processors([processor])
    else:
        add_trace_processor(processor)

    _processor = processor

    # Register shutdown handler
    atexit.register(_shutdown_handler)

    return processor


def get_run_config(
    group_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> RunConfig:
    """Create a RunConfig with tracing enabled.

    Args:
        group_id: Optional conversation/session ID for grouping traces
        metadata: Optional metadata to attach to the trace

    Returns:
        RunConfig with sensitive data capture enabled
    """
    return RunConfig(
        trace_include_sensitive_data=True,
        group_id=group_id,
        trace_metadata=metadata,
    )


def _shutdown_handler():
    """Cleanup handler called at process exit."""
    global _processor
    if _processor is not None:
        try:
            _processor.force_flush()
            _processor.shutdown()
        except Exception:
            # Intentionally suppress shutdown errors to avoid interfering with process exit,
            # but log them for observability.
            logging.getLogger(__name__).warning(
                "Error while flushing/shutting down Celesto trace processor during atexit",
                exc_info=True,
            )


# Convenience re-exports
__all__ = [
    "CelestoExporter",
    "setup_celesto_tracing",
    "get_run_config",
]
