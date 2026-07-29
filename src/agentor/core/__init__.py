from typing import TYPE_CHECKING

# schema is a dependency-free leaf module, so it stays eager. agent is not: it
# pulls the engine (~1.2s) and imports agentor.a2a, which imports this package
# back for JSONRPCReturnCodes. Resolving agent lazily keeps `import agentor.a2a`
# cheap and breaks that cycle.
from .schema import JSONRPCErrorCodes, JSONRPCReturnCodes

if TYPE_CHECKING:
    from .agent import Agentor, get_dummy_weather

__all__ = [
    "Agentor",
    "get_dummy_weather",
    "JSONRPCReturnCodes",
    "JSONRPCErrorCodes",
]


def __getattr__(name):
    if name in ("Agentor", "get_dummy_weather"):
        from . import agent

        value = getattr(agent, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
