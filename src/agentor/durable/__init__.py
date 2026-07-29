"""Deprecated: durability now lives in the engine.

DurableAgent was a second agent implementation that existed only because
durability was unreachable through the openai-agents engine. The native engine
persists its own event stream, so the separate class is gone.

    from agentor import Agentor
    from agentor.engine.store import FileStore

    agent = Agentor(name="Agent", tools=[...], engine="native", store=FileStore("runs"))
    result = agent.run("do the thing")
    ...
    agent.resume(result.run_id)   # continue after a crash
"""

from agentor.engine.events import RunResult
from agentor.engine.store import FileStore, MemoryStore, Store

__all__ = ["FileStore", "MemoryStore", "RunResult", "Store"]

_MIGRATION = (
    "DurableAgent has been removed. Durability is now part of the native "
    "engine, which persists its event stream:\n\n"
    "    from agentor import Agentor\n"
    "    from agentor.engine.store import FileStore\n\n"
    "    agent = Agentor(name=..., tools=[...], engine='native', "
    "store=FileStore('runs'))\n"
    "    result = agent.run('...')\n"
    "    agent.resume(result.run_id)\n"
)


def __getattr__(name):
    if name == "DurableAgent":
        raise AttributeError(_MIGRATION)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
