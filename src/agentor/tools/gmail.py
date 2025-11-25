import json
import logging
import os
from typing import List, Optional

from agentor.tools.base import BaseTool, capability

try:
    from superauth.google import GmailAPI, load_user_credentials
    from superauth.google.creds import CredentialRecord
except ImportError:  # pragma: no cover - optional dependency
    GmailAPI = None
    load_user_credentials = None
    CredentialRecord = None

logger = logging.getLogger(__name__)


class GmailTool(BaseTool):
    name = "gmail"
    description = (
        "Read-only Gmail helper for listing, searching, and fetching messages."
    )

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        credentials: Optional["CredentialRecord"] = None,
    ):
        """
        Initialize the Gmail tool.

        Args:
            credentials_path: Path to a saved user credentials JSON file produced by
                superauth. Defaults to the `GOOGLE_USER_CREDENTIALS` env var or
                `credentials.json`.
            credentials: Pre-loaded credentials object. If provided, overrides
                credentials_path.
            api_key: Optional API key for MCP use; not required for local usage.
        """
        super().__init__(credentials)

        if GmailAPI is None or load_user_credentials is None:
            raise ImportError(
                "superauth is not installed. Install with `pip install agentor[google]`."
            )

        if credentials is None:
            credentials_path = credentials_path or os.environ.get(
                "GOOGLE_USER_CREDENTIALS", "credentials.json"
            )
            try:
                credentials = load_user_credentials(credentials_path)
            except FileNotFoundError as exc:
                raise FileNotFoundError(
                    f"Credentials file not found at '{credentials_path}'. "
                    "Provide a valid path or set GOOGLE_USER_CREDENTIALS."
                ) from exc

        self.gmail = GmailAPI(credentials)

    @staticmethod
    def _clamp_limit(limit: int, *, default: int = 20, max_limit: int = 50) -> int:
        try:
            value = int(limit)
        except (TypeError, ValueError):
            return default
        return max(1, min(value, max_limit))

    def _run_gmail(self, func, **kwargs) -> str:
        try:
            data = func(**kwargs)
            return json.dumps(data)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Gmail tool error")
            return f"Error: {exc}"

    @capability
    def search_messages(
        self,
        query: str,
        label_ids: Optional[List[str]] = None,
        after: Optional[str] = None,
        before: Optional[str] = None,
        limit: int = 20,
    ) -> str:
        """
        Search Gmail using the same query syntax as the web UI.

        Examples: `from:alice has:attachment newer_than:7d`
        """
        if not query:
            return "Error: query is required to search messages."

        return self._run_gmail(
            self.gmail.search_messages,
            query=query,
            label_ids=label_ids,
            after=after,
            before=before,
            limit=self._clamp_limit(limit),
        )

    @capability
    def list_messages(
        self,
        label_ids: Optional[List[str]] = None,
        q: Optional[str] = None,
        limit: int = 20,
        page_token: Optional[str] = None,
        include_spam_trash: bool = False,
    ) -> str:
        """
        List message IDs (fast, metadata-only).

        Args:
            label_ids: Optional Gmail label IDs to filter by.
            q: Optional Gmail query string.
            limit: Number of messages to return (1-50).
            page_token: Pagination token returned by a previous call.
            include_spam_trash: Whether to include spam and trash.
        """
        return self._run_gmail(
            self.gmail.list_messages,
            label_ids=label_ids,
            q=q,
            limit=self._clamp_limit(limit),
            page_token=page_token,
            include_spam_trash=include_spam_trash,
        )

    @capability
    def get_message(self, message_id: str) -> str:
        """
        Fetch a single Gmail message (metadata only).

        Args:
            message_id: Gmail message ID.
        """
        if not message_id:
            return "Error: message_id is required."
        return self._run_gmail(self.gmail.get_message, message_id=message_id)

    @capability
    def get_message_body(
        self,
        message_id: str,
        prefer: str = "text",
        limit: int = 50000,
    ) -> str:
        """
        Fetch a single Gmail message body for display or summarization.

        Args:
            message_id: Gmail message ID.
            prefer: "text" or "html".
            limit: Max characters to return for the selected body.
        """
        if not message_id:
            return "Error: message_id is required."

        return self._run_gmail(
            self.gmail.get_message_body,
            message_id=message_id,
            prefer=prefer,
            max_chars=self._clamp_limit(limit, default=50000, max_limit=50000),
        )
