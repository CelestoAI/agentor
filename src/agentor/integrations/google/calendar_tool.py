from __future__ import annotations

import datetime as dt
import typing as t

import backoff
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Import here to avoid circular imports
if t.TYPE_CHECKING:
    from .creds import CredentialRecord


CalendarEvent = dict[str, t.Any]


# Any of these scopes allow creating or modifying calendar events
_WRITE_CAPABLE_SCOPES = frozenset(
    {
        "https://www.googleapis.com/auth/calendar.events",
        "https://www.googleapis.com/auth/calendar",
    }
)


class CalendarEventTimeBlock(t.TypedDict):
    dateTime: str | dt.datetime
    timeZone: t.NotRequired[str]


class CalendarAttendee(t.TypedDict, total=False):
    email: str
    displayName: str
    optional: bool


class CalendarEventPayload(t.TypedDict, total=False):
    summary: str
    description: str
    start: CalendarEventTimeBlock | dt.datetime | str
    end: CalendarEventTimeBlock | dt.datetime | str
    attendees: list[CalendarAttendee]
    location: str
    conferenceData: dict[str, t.Any]
    reminders: dict[str, t.Any]


def _rfc3339(ts: str | dt.datetime | None) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        # Accept "YYYY-MM-DD" or full ISO8601; convert to RFC3339
        if len(ts) == 10:
            return ts + "T00:00:00Z"
        return ts
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return ts.isoformat()


def _is_transient(err: Exception) -> bool:
    if isinstance(err, HttpError) and getattr(err, "resp", None):
        return err.resp.status in (429, 500, 502, 503, 504)
    return False


def _credentials_have_write_access(creds: Credentials) -> bool:
    scopes = getattr(creds, "scopes", None) or []
    scope_set = {scope for scope in scopes if scope}
    if scope_set.intersection(_WRITE_CAPABLE_SCOPES):
        return True

    has_scopes = getattr(creds, "has_scopes", None)
    if callable(has_scopes):
        for scope in _WRITE_CAPABLE_SCOPES:
            try:
                if has_scopes([scope]):
                    return True
            except Exception:
                # Ignore unexpected failures and fall back to default False
                continue

    return False


class CalendarService:
    """
    Google Calendar integration with Google OAuth2 credentials.
    Accepts either Credentials or CredentialRecord objects.
    """

    def __init__(
        self, credentials: Credentials | CredentialRecord, *, logger: t.Any = None
    ):
        """
        Args:
            credentials: Google OAuth2 credentials with Calendar scope, or CredentialRecord
            logger: Optional logger instance
        """
        from .creds import CredentialRecord  # Import here to avoid circular imports

        if isinstance(credentials, CredentialRecord):
            self._credentials = credentials.to_credentials()
        else:
            self._credentials = credentials
        self._logger = logger
        self._service = None

    def _svc(self):
        """Get or create Calendar service."""
        if self._service is None:
            self._service = build(
                "calendar", "v3", credentials=self._credentials, cache_discovery=False
            )
        return self._service

    def list_events(
        self,
        *,
        calendar_id: str = "primary",
        time_min: str | dt.datetime | None = None,
        time_max: str | dt.datetime | None = None,
        max_results: int = 50,
        single_events: bool = True,
        order_by: str = "startTime",
        page_token: str | None = None,
    ) -> dict:
        """
        List Google Calendar events.

        Args:
            calendar_id: Calendar ID (default "primary")
            time_min: Lower bound (inclusive) for event start time
            time_max: Upper bound (exclusive) for event start time
            max_results: Max results (1-250)
            single_events: Whether to expand recurring events
            order_by: Sort order ("startTime" or "updated")
            page_token: For pagination

        Returns:
            {"events": [CalendarEvent, ...], "nextPageToken": str | None}
        """
        max_results = max(1, min(int(max_results or 50), 250))
        svc = self._svc()

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_time=20,
            jitter=None,
            giveup=lambda e: not _is_transient(e),
        )
        def _list():
            return (
                svc.events()
                .list(
                    calendarId=calendar_id,
                    timeMin=_rfc3339(time_min),
                    timeMax=_rfc3339(time_max),
                    maxResults=max_results,
                    singleEvents=single_events,
                    orderBy=order_by,
                    pageToken=page_token,
                )
                .execute()
            )

        res = _list() or {}
        return {
            "events": res.get("items", []),
            "nextPageToken": res.get("nextPageToken"),
        }

    def get_event(
        self,
        *,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict:
        """
        Get a single Google Calendar event.

        Args:
            event_id: Event ID
            calendar_id: Calendar ID (default "primary")

        Returns:
            {"event": CalendarEvent}
        """
        svc = self._svc()

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_time=20,
            jitter=None,
            giveup=lambda e: not _is_transient(e),
        )
        def _get():
            return svc.events().get(calendarId=calendar_id, eventId=event_id).execute()

        return {"event": _get()}

    def create_event(
        self,
        *,
        event: CalendarEventPayload | CalendarEvent,
        calendar_id: str = "primary",
    ) -> dict:
        """
        Create a Google Calendar event.

        Args:
            event: Event payload matching the Google Calendar API schema
            calendar_id: Calendar ID (default "primary")

        Returns:
            {"event": CalendarEvent}

        Notes:
            `start` and `end` accept timezone-aware `datetime` objects, RFC3339 strings,
            or dicts containing a `dateTime` field (and optional `timeZone`).

        Example:
            >>> calendar = CalendarService(creds)
            >>> calendar.create_event(
            ...     event={
            ...         "summary": "Weekly sync",
            ...         "description": "Process updates and blockers",
            ...         "start": dt.datetime(2024, 6, 18, 15, 0, tzinfo=dt.timezone.utc),
            ...         "end": "2024-06-18T19:30:00Z",
            ...         "attendees": [{"email": "alice@example.com"}],
            ...     }
            ... )
        """

        if not _credentials_have_write_access(self._credentials):
            available = sorted(
                scope
                for scope in (getattr(self._credentials, "scopes", None) or [])
                if scope
            )
            message = (
                "Google Calendar credentials do not include write access. "
                "Re-authorize with the https://www.googleapis.com/auth/calendar.events scope "
                "or the broader https://www.googleapis.com/auth/calendar scope. "
                f"Current scopes: {', '.join(available) if available else '<none>'}."
            )
            if self._logger:
                self._logger.warning(message)
            raise PermissionError(message)

        def _normalize_time(block: t.Any) -> dict:
            if isinstance(block, dt.datetime):
                return {"dateTime": _rfc3339(block)}
            if isinstance(block, str):
                if len(block) == 10:
                    raise ValueError("dateTime string must include a time component")
                return {"dateTime": _rfc3339(block)}
            if isinstance(block, dict):
                block = dict(block)
                if "date" in block:
                    raise ValueError("start/end blocks must use dateTime, not date")
                if "dateTime" not in block:
                    raise ValueError("start/end blocks require a dateTime field")

                value = block["dateTime"]
                if not isinstance(value, (str, dt.datetime)):
                    raise TypeError("dateTime must be a datetime or RFC3339 string")
                if isinstance(value, str) and len(value) == 10:
                    raise ValueError("dateTime string must include a time component")

                block["dateTime"] = _rfc3339(value)
                return block

            raise TypeError(
                "start/end must be datetime, RFC3339 string, or mapping with dateTime field"
            )

        body = dict(event)
        for key in ("start", "end", "originalStartTime"):
            if key in body:
                body[key] = _normalize_time(body[key])

        svc = self._svc()

        @backoff.on_exception(
            backoff.expo,
            Exception,
            max_time=20,
            jitter=None,
            giveup=lambda e: not _is_transient(e),
        )
        def _insert():
            return (
                svc.events()
                .insert(
                    calendarId=calendar_id,
                    body=body,
                    conferenceDataVersion=1 if body.get("conferenceData") else 0,
                )
                .execute()
            )

        return {"event": _insert()}
