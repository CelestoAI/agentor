from .integrations.google import GmailTool, CalendarTool
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from zerozen.memory.api import Memory


@dataclass
class AppContext:
    user_id: str
    gmail: GmailTool
    calendar: CalendarTool
    memory: "Memory"
