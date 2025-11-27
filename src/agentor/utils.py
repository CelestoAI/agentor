from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from superauth.google import CalendarAPI, GmailAPI

if TYPE_CHECKING:
    from agentor.memory.api import Memory


@dataclass
class GoogleAPIs:
    gmail: GmailAPI | None = None
    calendar: CalendarAPI | None = None


@dataclass
class CoreServices:
    memory: Memory | None = None


@dataclass
class AppContext:
    user_id: str | None = None
    api_providers: GoogleAPIs = None
    core: CoreServices = None

    def __post_init__(self):
        if self.api_providers is None:
            self.api_providers = GoogleAPIs()
        if self.core is None:
            self.core = CoreServices()
