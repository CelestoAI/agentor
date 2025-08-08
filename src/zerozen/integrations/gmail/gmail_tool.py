# gmail_tool.py
from __future__ import annotations
import datetime as dt
import typing as t

import backoff
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


MessageSummary = dict[str, t.Any]


def _iso_to_epoch(iso: str) -> int:
    """Accepts 'YYYY-MM-DD' or any ISO8601; treats naive as UTC."""
    if not iso:
        return 0
    if len(iso) == 10:  # 'YYYY-MM-DD'
        iso = iso + "T00:00:00Z"
    clean = iso[:-1] if iso.endswith("Z") else iso
    d = dt.datetime.fromisoformat(clean)
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def _metadata_headers() -> list[str]:
    return ["From", "To", "Cc", "Subject", "Date"]


def _normalize_metadata(msg: dict) -> MessageSummary:
    payload = msg.get("payload") or {}
    headers = {h["name"].lower(): h.get("value", "") for h in payload.get("headers", [])}
    return {
        "id": msg["id"],
        "threadId": msg.get("threadId"),
        "subject": headers.get("subject", ""),
        "from": headers.get("from", ""),
        "to": headers.get("to", ""),
        "cc": headers.get("cc", ""),
        "date": headers.get("date", ""),
        "snippet": msg.get("snippet", ""),
        "labels": msg.get("labelIds", []),
    }


def _build_query(query: str, after: str | None, before: str | None) -> str:
    parts: list[str] = []
    if query:
        parts.append(query)
    if after:
        parts.append(f"after:{_iso_to_epoch(after)}")
    if before:
        parts.append(f"before:{_iso_to_epoch(before)}")
    return " ".join(parts).strip()


def _is_transient(err: Exception) -> bool:
    if isinstance(err, HttpError) and getattr(err, "resp", None):
        return err.resp.status in (429, 500, 502, 503, 504)
    return False


class GmailTool:
    """
    Search-only Gmail integration.
    Keep this class's API stable so you can add get_message/reply later without churn.
    """

    def __init__(
        self,
        creds_provider: t.Callable[[str], Credentials],
        *,
        logger: t.Any = None,
    ):
        """
        creds_provider(user_id) -> google.oauth2.credentials.Credentials
        The provider should return a valid Credentials object (with refresh token).
        """
        self._creds_provider = creds_provider
        self._logger = logger

    def _svc(self, user_id: str):
        creds = self._creds_provider(user_id)
        return build("gmail", "v1", credentials=creds, cache_discovery=False)

    def search_messages(
        self,
        *,
        user_id: str,
        query: str,
        label_ids: list[str] | None = None,
        after: str | None = None,   # 'YYYY-MM-DD' or ISO8601
        before: str | None = None,  # 'YYYY-MM-DD' or ISO8601
        limit: int = 20,
    ) -> dict:
        """
        Returns: {"messages": [MessageSummary, ...]}
        """
        limit = max(1, min(int(limit or 20), 50))
        q = _build_query(query, after, before)
        svc = self._svc(user_id)

        @backoff.on_exception(backoff.expo, Exception, max_time=20, jitter=None,
                              giveup=lambda e: not _is_transient(e))
        def _list():
            return svc.users().messages().list(
                userId="me",
                q=q,
                labelIds=label_ids or [],
                maxResults=limit,
            ).execute()

        res = _list()
        ids = [m["id"] for m in res.get("messages", [])]

        summaries: list[MessageSummary] = []

        for mid in ids:
            @backoff.on_exception(backoff.expo, Exception, max_time=20, jitter=None,
                                  giveup=lambda e: not _is_transient(e))
            def _get():
                return svc.users().messages().get(
                    userId="me",
                    id=mid,
                    format="metadata",
                    metadataHeaders=_metadata_headers(),
                ).execute()

            msg = _get()
            summaries.append(_normalize_metadata(msg))

        return {"messages": summaries}
