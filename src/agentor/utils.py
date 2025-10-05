from dataclasses import dataclass

from agentor.memory.api import Memory

from .integrations.google import CalendarService, GmailService


@dataclass
class GoogleServices:
    gmail: GmailService | None = None
    calendar: CalendarService | None = None


@dataclass
class CoreServices:
    memory: Memory | None = None


@dataclass
class AppContext:
    user_id: str | None = None
    services: GoogleServices = None
    core: CoreServices = None

    def __post_init__(self):
        if self.services is None:
            self.services = GoogleServices()
        if self.core is None:
            self.core = CoreServices()
