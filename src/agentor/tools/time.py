from datetime import datetime
import pytz
from agentor.tools.base import BaseTool


class CurrentTime(BaseTool):
    name = "get_current_time"
    description = "Get the current time in a specific timezone"

    def run(self, timezone: str = "UTC") -> str:
        """
        Get the current time.

        Args:
            timezone: The timezone to get the time for (e.g. 'UTC', 'America/New_York').
        """
        try:
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except pytz.UnknownTimeZoneError:
            return f"Error: Unknown timezone '{timezone}'"
