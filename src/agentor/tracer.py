"""Celesto tracing.

The exporter used to reverse-engineer openai-agents' span objects through
`hasattr` chains, and could only see runs that went through that SDK. Tracing
is now a projection of the engine's own event stream, so it covers every run
by construction. The implementation lives in `agentor.engine.tracing`; this
module keeps the public entry point.

Usage:
    from agentor.tracer import setup_celesto_tracing

    tracer = setup_celesto_tracing(
        endpoint="https://api.celesto.ai/v1/traces/ingest",
        token="your-celesto-api-token",
    )
    agent = Agentor(name="my_agent", tracer=tracer)

Agents built with `Agentor(...)` configure this automatically from
`CELESTO_API_KEY`, so calling it by hand is only needed for a bare `AgentLoop`.
"""

from agentor.engine.tracing import CelestoTracer, TraceCollector


def setup_celesto_tracing(
    endpoint: str,
    token: str,
    *,
    timeout: float = 10.0,
) -> CelestoTracer:
    """Build a tracer that ships runs to the Celesto ingest API.

    Args:
        endpoint: Celesto ingest API URL.
        token: Bearer token for authentication.
        timeout: HTTP request timeout in seconds.

    Returns:
        A `CelestoTracer`, which `AgentLoop`/`Agentor` accept as `tracer=`.
    """
    return CelestoTracer(endpoint=endpoint, token=token, timeout=timeout)


__all__ = [
    "CelestoTracer",
    "TraceCollector",
    "setup_celesto_tracing",
]
