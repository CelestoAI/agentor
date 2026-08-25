"""Celesto tracing for the native engine.

The event stream already describes a run completely, so a trace is a direct
projection of it rather than a second representation. Nothing here reads the
engine's internals, which is what made the openai-agents exporter fragile.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from agentor.engine.events import Event

logger = logging.getLogger(__name__)


def _iso(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


class TraceCollector:
    """Builds Celesto trace/span payloads from engine events.

    One trace per run; a `generation` span per model call and a `function`
    span per tool call, both parented to the run's agent span.
    """

    def __init__(
        self,
        workflow_name: str,
        group_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.trace_id = f"trace_{uuid.uuid4().hex}"
        self.workflow_name = workflow_name
        self.group_id = group_id
        self.metadata = metadata
        self.agent_span_id = f"span_{uuid.uuid4().hex}"
        self.items: List[Dict[str, Any]] = []

    def _span(
        self, span_data: Dict[str, Any], event: Event, parent: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "object": "trace.span",
            "span_id": f"span_{uuid.uuid4().hex}",
            "trace_id": self.trace_id,
            "parent_id": parent or self.agent_span_id,
            "started_at": _iso(event.started_at),
            "ended_at": _iso(event.ended_at),
            "span_data": span_data,
        }

    def handle(self, event: Event) -> None:
        if event.type == "run_start":
            self.items.append(
                {
                    "object": "trace",
                    "id": self.trace_id,
                    "workflow_name": self.workflow_name,
                    "group_id": self.group_id,
                    "metadata": self.metadata,
                }
            )
            self._agent_started_at = event.started_at
            self._agent_name = event.agent
            self._agent_model = event.model

        elif event.type == "generation":
            span_data = {
                "type": "generation",
                "model": event.model,
                "input": event.messages,
                "output": event.text,
                "tool_calls": event.calls,
                "usage": {
                    "input_tokens": event.usage.input_tokens,
                    "output_tokens": event.usage.output_tokens,
                    "total_tokens": event.usage.total_tokens,
                }
                if event.usage
                else None,
            }
            # only when the provider returned any, so existing payloads keep
            # their shape
            if event.reasoning:
                span_data["reasoning"] = event.reasoning
            self.items.append(self._span(span_data, event))

        elif event.type == "tool_result":
            span = self._span(
                {
                    "type": "function",
                    "name": event.name,
                    "input": event.args,
                    "output": event.result,
                },
                event,
            )
            if event.error:
                span["error"] = {"message": event.error}
            self.items.append(span)

        elif event.type == "run_end":
            span = {
                "object": "trace.span",
                "span_id": self.agent_span_id,
                "trace_id": self.trace_id,
                "parent_id": None,
                "started_at": _iso(event.started_at),
                "ended_at": _iso(event.ended_at),
                "span_data": {
                    "type": "agent",
                    "name": getattr(self, "_agent_name", self.workflow_name),
                    "model": getattr(self, "_agent_model", None),
                    "output": event.text,
                    "status": event.status,
                    "usage": {
                        "input_tokens": event.usage.input_tokens,
                        "output_tokens": event.usage.output_tokens,
                        "total_tokens": event.usage.total_tokens,
                    }
                    if event.usage
                    else None,
                },
            }
            if event.error:
                span["error"] = {"message": event.error}
            self.items.append(span)


class CelestoTracer:
    """Collects a run's events and ships them to the Celesto ingest API."""

    def __init__(self, endpoint: str, token: str, timeout: float = 10.0):
        self.endpoint = endpoint
        self.token = token
        self.timeout = timeout

    def collector(self, workflow_name: str, **kwargs: Any) -> TraceCollector:
        return TraceCollector(workflow_name, **kwargs)

    def export(self, collector: TraceCollector) -> None:
        if not collector.items:
            return
        import httpx

        try:
            response = httpx.post(
                self.endpoint,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={"data": collector.items},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as e:
            # Tracing must never take down the agent run.
            logger.warning("Failed to export traces to Celesto: %s", e)
