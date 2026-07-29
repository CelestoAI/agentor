from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

# superauth pulls in google-api-python-client (~99MB) and ships with the
# `google` extra. These names are only ever used as annotations here, so
# postponed evaluation keeps AppContext importable without it installed.
if TYPE_CHECKING:
    from superauth.google import CalendarAPI, GmailAPI


@dataclass
class GoogleAPIs:
    gmail: GmailAPI | None = None
    calendar: CalendarAPI | None = None


@dataclass
class AppContext:
    user_id: str | None = None
    api_providers: GoogleAPIs = None

    def __post_init__(self):
        if self.api_providers is None:
            self.api_providers = GoogleAPIs()
