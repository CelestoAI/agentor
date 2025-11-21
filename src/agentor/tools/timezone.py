from datetime import datetime

import pytz

from agentor.tools.base import BaseTool, capability


class TimezoneTool(BaseTool):
    name = "timezone"
    description = "Get current time in different timezones"

    @capability
    def get_current_time(self, timezone: str = "UTC") -> str:
        """
        Get the current time in a specific timezone.

        Args:
            timezone: The timezone to get the time for (e.g. 'UTC', 'America/New_York', 'Europe/London').
        """
        try:
            tz = pytz.timezone(timezone)
            now = datetime.now(tz)
            return now.strftime("%Y-%m-%d %H:%M:%S %Z")
        except pytz.UnknownTimeZoneError:
            return f"Error: Unknown timezone '{timezone}'"

    @capability
    def list_timezones(self) -> str:
        """
        List all available timezones.
        """
        timezones = pytz.all_timezones
        # Return first 50 timezones to avoid overwhelming output
        sample = timezones[:50]
        return "Available timezones (showing first 50):\n" + "\n".join(sample)
