"""Model settings.

A small, provider-neutral set of knobs. Anything not covered here goes in
`extra` and is passed through untouched, so a provider-specific parameter
never requires a change to this file.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union


@dataclass
class ModelSettings:
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    max_tokens: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    seed: Optional[int] = None
    stop: Optional[Union[str, List[str]]] = None
    #: passed straight through, for provider-specific parameters
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_params(self) -> Dict[str, Any]:
        """Request parameters, omitting anything left unset."""
        params = {
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "frequency_penalty": self.frequency_penalty,
            "presence_penalty": self.presence_penalty,
            "seed": self.seed,
            "stop": self.stop,
        }
        params = {key: value for key, value in params.items() if value is not None}
        params.update(self.extra)
        return params
