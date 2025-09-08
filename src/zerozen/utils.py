from .integrations.google import GmailTool, CalendarTool
from dataclasses import dataclass
from zerozen.memory.api import Memory


@dataclass
class AppContext:
    user_id: str | None = None
    gmail: GmailTool | None = None
    calendar: CalendarTool | None = None
    memory: Memory | None = None
