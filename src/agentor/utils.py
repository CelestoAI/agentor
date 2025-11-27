from dataclasses import dataclass

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
