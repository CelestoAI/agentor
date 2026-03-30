import json
import logging
from datetime import datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

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
        """Clamp list limits to a safe integer range."""
        try:
            value = int(limit)
        except (TypeError, ValueError):
            return default
        return max(1, min(value, max_limit))

    @staticmethod
    def _normalize_datetime(dt_string: str) -> str:
        """Validate datetime includes an explicit timezone offset."""
        if not dt_string:
            raise ValueError("Datetime is required and must include timezone.")

        try:
            parsed = datetime.fromisoformat(dt_string.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(
                "Invalid datetime format. Use ISO 8601 with timezone (Z or ±HH:MM)."
            ) from exc

        if parsed.tzinfo is None:
            raise ValueError("Datetime must include timezone (Z or ±HH:MM).")

        return dt_string

    def _get_calendar_timezone(self, calendar_id: str = "primary") -> str:
        """Get the timezone configured for a calendar.

        Args:
            calendar_id: Calendar ID (default "primary").

        Returns:
            IANA timezone string (e.g., "America/New_York").
        """
        try:
            calendar = self.service.calendarList().get(calendarId=calendar_id).execute()
            return calendar.get("timeZone", "UTC")
        except Exception:
            logger.debug(f"Failed to fetch timezone for {calendar_id}, defaulting to UTC")
            return "UTC"

    @staticmethod
    def _event_bounds(
        event: dict, calendar_timezone: str = "UTC"
    ) -> tuple[datetime, datetime] | None:
        """Extract normalized event time bounds from timed or all-day events."""
        start_info = event.get("start", {})
        end_info = event.get("end", {})

        start_dt = start_info.get("dateTime")
        end_dt = end_info.get("dateTime")
        if start_dt and end_dt:
            return (
                datetime.fromisoformat(start_dt.replace("Z", "+00:00")),
                datetime.fromisoformat(end_dt.replace("Z", "+00:00")),
            )

        start_date = start_info.get("date")
        end_date = end_info.get("date")
        if start_date and end_date:
            tz = ZoneInfo(calendar_timezone)
            return (
                datetime.fromisoformat(f"{start_date}T00:00:00").replace(tzinfo=tz),
                datetime.fromisoformat(f"{end_date}T00:00:00").replace(tzinfo=tz),
            )

        return None

    @capability
    def list_events(
        self,
        start_time: str,
        end_time: str,
        calendar_id: str = "primary",
        limit: int = 20,
        query: Optional[str] = None,
    ) -> str:
        """List events in a time window.

        Follows nextPageToken to fetch all events across pages.
        """
        try:
            start_time = self._normalize_datetime(start_time)
            end_time = self._normalize_datetime(end_time)

            all_items = []
            page_token = None
            max_results = self._clamp_limit(limit, max_limit=2500)

            # Fetch pages until we have limit items or run out of pages
            while len(all_items) < limit:
                events_result = (
                    self.service.events()
                    .list(
                        calendarId=calendar_id,
                        timeMin=start_time,
                        timeMax=end_time,
                        maxResults=max_results,
                        singleEvents=True,
                        orderBy="startTime",
                        q=query,
                        pageToken=page_token,
                    )
                    .execute()
                )

                all_items.extend(events_result.get("items", []))
                page_token = events_result.get("nextPageToken")

                if not page_token:
                    # No more pages available
                    break

            return json.dumps(all_items[:limit])
        except ValueError as exc:
            return f"Error: {exc}"
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

        try:
            start_time = self._normalize_datetime(start_time)
            end_time = self._normalize_datetime(end_time)

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
        except ValueError as exc:
            return f"Error: {exc}"
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
        try:
            start_time = self._normalize_datetime(start_time)
            end_time = self._normalize_datetime(end_time)

            if meeting_minutes <= 0:
                raise ValueError("meeting_minutes must be greater than 0.")

            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))

            if end_dt <= start_dt:
                raise ValueError("end_time must be after start_time.")

            raw = self.list_events(
                start_time=start_time,
                end_time=end_time,
                calendar_id=calendar_id,
                limit=250,
            )

            if raw.startswith("Error:"):
                return raw

            events = json.loads(raw)
            calendar_timezone = self._get_calendar_timezone(calendar_id)
            busy_ranges: list[tuple[datetime, datetime]] = []

            for event in events:
                bounds = self._event_bounds(event, calendar_timezone)
                if bounds:
                    busy_ranges.append(bounds)

            busy_ranges.sort(key=lambda span: span[0])

            free_slots = []
            cursor = start_dt
            needed = timedelta(minutes=meeting_minutes)

            for busy_start, busy_end in busy_ranges:
                if (busy_start - cursor) >= needed:
                    free_slots.append(
                        {"start": cursor.isoformat(), "end": busy_start.isoformat()}
                    )
                cursor = max(cursor, busy_end)

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
        except ValueError as exc:
            return f"Error: {exc}"
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
            added_count = 0
            for email in guest_emails:
                if email not in existing_emails:
                    attendees.append({"email": email})
                    existing_emails.add(email)
                    added_count += 1

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
                    "message": f"Added {added_count} guest(s) to event.",
                    "event_id": updated.get("id"),
                    "attendees": updated.get("attendees", []),
                }
            )
        except Exception as exc:
            logger.exception("Calendar add_guests error")
            return f"Error: {exc}"
