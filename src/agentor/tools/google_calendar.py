import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from agentor.tools.base import BaseTool, capability

try:
    from googleapiclient.discovery import build
except ImportError:  # pragma: no cover - optional dependency
    build = None

logger = logging.getLogger(__name__)


class CalendarTool(BaseTool):
    name = "calendar"
    description = (
        "Google Calendar helper for listing, creating events, and finding free slots."
    )

    def __init__(self, credentials, api_key: Optional[str] = None):
        """
        Initialize the Calendar tool.

        Args:
            credentials: Google Credentials object (from user's stored token).
                        Can be loaded from database and reconstructed using:
                        from google.oauth2.credentials import Credentials
                        creds = Credentials.from_authorized_user_info(creds_dict)
            api_key: Optional API key for MCP use.
        """
        super().__init__(api_key)

        if build is None:
            raise ImportError(
                "Google API client not installed. Install with: "
                "pip install google-api-python-client"
            )

        if credentials is None:
            raise ValueError(
                "Credentials object is required. "
                "For SaaS, pass pre-loaded credentials from user's stored token."
            )

        self.service = build("calendar", "v3", credentials=credentials)

    @staticmethod
    def _clamp_limit(limit: int, *, default: int = 20, max_limit: int = 100) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            return default
        return max(1, min(value, max_limit))

    @staticmethod
    def _normalize_datetime(dt_string: str) -> str:
        """Ensure datetime has timezone info (append 'Z' for UTC if missing)."""
        if dt_string and not (
            dt_string.endswith("Z") or "+" in dt_string or "-" in dt_string[-6:]
        ):
            return dt_string + "Z"
        return dt_string

    @capability
    def list_events(
        self,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        limit: int = 20,
        query: Optional[str] = None,
    ) -> str:
        """List events in a time window."""
        start_time = self._normalize_datetime(start_time)
        end_time = self._normalize_datetime(end_time)
        try:
            events_result = (
                self.service.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=start_time,
                    timeMax=end_time,
                    maxResults=self._clamp_limit(limit),
                    singleEvents=True,
                    orderBy="startTime",
                    q=query,
                )
                .execute()
            )
            return json.dumps(events_result.get("items", []))
        except Exception as exc:
            logger.exception("Calendar list_events error")
            return f"Error: {exc}"

    @capability
    def create_event(
        self,
        title: str,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        description: Optional[str] = None,
        location: Optional[str] = None,
    ) -> str:
        """Create a calendar event."""
        if not title:
            return "Error: title is required."

        start_time = self._normalize_datetime(start_time)
        end_time = self._normalize_datetime(end_time)

        try:
            event = {
                "summary": title,
                "description": description or "",
                "location": location or "",
                "start": {"dateTime": start_time},
                "end": {"dateTime": end_time},
            }

            created = (
                self.service.events()
                .insert(calendarId=calendar_id, body=event)
                .execute()
            )
            return json.dumps(created)
        except Exception as exc:
            logger.exception("Calendar create_event error")
            return f"Error: {exc}"

    @capability
    def find_free_slots(
        self,
        start_time: str,
        end_time: str,
        meeting_minutes: int = 30,
        calendar_id: str = "primary",
        limit: int = 10,
    ) -> str:
        """Find free time slots."""
        start_time = self._normalize_datetime(start_time)
        end_time = self._normalize_datetime(end_time)

        try:
            raw = self.list_events(
                start_time=start_time,
                end_time=end_time,
                calendar_id=calendar_id,
                limit=250,
            )

            if raw.startswith("Error:"):
                return raw

            events = json.loads(raw)
            busy_ranges = []

            for event in events:
                start = event.get("start", {}).get("dateTime")
                end = event.get("end", {}).get("dateTime")
                if start and end:
                    busy_ranges.append((start, end))

            busy_ranges.sort()

            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            free_slots = []
            cursor = start_dt
            needed = timedelta(minutes=meeting_minutes)

            for busy_start_str, busy_end_str in busy_ranges:
                busy_start = datetime.fromisoformat(
                    busy_start_str.replace("Z", "+00:00")
                )
                if (busy_start - cursor) >= needed:
                    free_slots.append(
                        {"start": cursor.isoformat(), "end": busy_start.isoformat()}
                    )
                cursor = max(
                    cursor, datetime.fromisoformat(busy_end_str.replace("Z", "+00:00"))
                )

            if (end_dt - cursor) >= needed:
                free_slots.append(
                    {"start": cursor.isoformat(), "end": end_dt.isoformat()}
                )

            return json.dumps(
                {
                    "window_start": start_time,
                    "window_end": end_time,
                    "meeting_minutes": meeting_minutes,
                    "free_slots": free_slots[:limit],
                }
            )
        except Exception as exc:
            logger.exception("Calendar find_free_slots error")
            return f"Error: {exc}"

    @capability
    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> str:
        """Delete a calendar event."""
        if not event_id:
            return "Error: event_id is required."

        try:
            self.service.events().delete(
                calendarId=calendar_id, eventId=event_id
            ).execute()
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Event {event_id} deleted successfully.",
                }
            )
        except Exception as exc:
            logger.exception("Calendar delete_event error")
            return f"Error: {exc}"

    @capability
    def add_guests(
        self,
        event_id: str,
        guest_emails: list,
        calendar_id: str = "primary",
        send_notifications: bool = True,
    ) -> str:
        """Add guests to a calendar event."""
        if not event_id:
            return "Error: event_id is required."
        if not guest_emails or not isinstance(guest_emails, list):
            return "Error: guest_emails must be a non-empty list."

        try:
            event = (
                self.service.events()
                .get(calendarId=calendar_id, eventId=event_id)
                .execute()
            )

            existing_emails = {att.get("email") for att in event.get("attendees", [])}

            attendees = event.get("attendees", [])
            for email in guest_emails:
                if email not in existing_emails:
                    attendees.append({"email": email})

            event["attendees"] = attendees
            updated = (
                self.service.events()
                .update(
                    calendarId=calendar_id,
                    eventId=event_id,
                    body=event,
                    sendUpdates="all" if send_notifications else "none",
                )
                .execute()
            )

            return json.dumps(
                {
                    "status": "success",
                    "message": f"Added {len(guest_emails)} guest(s) to event.",
                    "event_id": updated.get("id"),
                    "attendees": updated.get("attendees", []),
                }
            )
        except Exception as exc:
            logger.exception("Calendar add_guests error")
            return f"Error: {exc}"
