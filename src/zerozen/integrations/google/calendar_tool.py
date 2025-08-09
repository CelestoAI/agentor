from __future__ import annotations
import datetime as dt
import typing as t

import backoff
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


CalendarEvent = dict[str, t.Any]


def _rfc3339(ts: str | dt.datetime | None) -> str | None:
    if ts is None:
        return None
    if isinstance(ts, str):
        # Accept YYYY-MM-DD or full ISO8601; convert to RFC3339
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


class CalendarTool:
    """
    Minimal Google Calendar read-only integration.
    """

    def __init__(
        self,
        creds_provider: t.Callable[[str], Credentials],
        *,
        logger: t.Any = None,
    ):
        self._creds_provider = creds_provider
        self._logger = logger

    def _svc(self, user_id: str):
        creds = self._creds_provider(user_id)
        return build("calendar", "v3", credentials=creds, cache_discovery=False)

    def list_events(
        self,
        *,
        user_id: str,
        calendar_id: str = "primary",
        time_min: str | dt.datetime | None = None,
        time_max: str | dt.datetime | None = None,
        max_results: int = 50,
        single_events: bool = True,
        order_by: str = "startTime",
        page_token: str | None = None,
    ) -> dict:
        """
        Returns: {"events": [CalendarEvent, ...], "nextPageToken": str | None}
        CalendarEvent fields: id, status, summary, description, start, end, location, attendees, hangoutLink, etc.
        """
        max_results = max(1, min(int(max_results or 50), 250))
        svc = self._svc(user_id)

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
        user_id: str,
        event_id: str,
        calendar_id: str = "primary",
    ) -> dict:
        """Return a single event as provided by the Calendar API."""
        svc = self._svc(user_id)

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
