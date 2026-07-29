"""Model settings.

A small, provider-neutral set of knobs. Anything else is accepted and passed
through, so a provider-specific parameter never requires a change here — and so
settings written against the type agentor exported before v0.1.0 keep working
instead of raising on an unexpected keyword.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

#: Accepted for compatibility with the previously exported settings type, but
#: meaningless to a chat-completions request. Forwarding them would earn a
#: provider 400, so they are dropped with a warning instead.
_UNSUPPORTED = frozenset(
    {
        "context_management",
        "include_usage",
        "prompt_cache_options",
        "prompt_cache_retention",
        "response_include",
        "retry",
        "truncation",
    }
)


@dataclass(init=False)
class ModelSettings:
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    parallel_tool_calls: Optional[bool] = None
    reasoning_effort: Optional[str] = None
    verbosity: Optional[str] = None
    top_logprobs: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None
    store: Optional[bool] = None
    #: passed straight through, for provider-specific parameters
    extra: Dict[str, Any] = field(default_factory=dict)

    def __init__(self, **kwargs: Any):
        known = [f for f in self.__dataclass_fields__ if f != "extra"]
        extra = dict(kwargs.pop("extra", None) or {})

        for name in list(kwargs):
            if name in known:
                continue
            value = kwargs.pop(name)
            if name in _UNSUPPORTED:
                logger.warning(
                    "ModelSettings.%s has no chat-completions equivalent and "
                    "was ignored.",
                    name,
                )
                continue
            # unrecognised but plausibly provider-specific: forward it
            extra[name] = value

        for name in known:
            setattr(self, name, kwargs.get(name))
        self.extra = extra

    def to_params(self) -> Dict[str, Any]:
        """Request parameters, omitting anything left unset."""
        params = {
            name: getattr(self, name)
            for name in self.__dataclass_fields__
            if name != "extra" and getattr(self, name) is not None
        }
        params.update(self.extra)
        return params
