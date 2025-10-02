# creds.py - Google OAuth credential management
"""
Google OAuth credential management with structured dataclasses.

This module provides:
- CredentialRecord: Structured dataclass for user credentials
- UserProviderMetadata: OAuth provider metadata for a specific user from backend
- UserInfo: User information from OAuth provider
- GoogleAccount: Per-user credential management (legacy)
- desktop_creds_provider_factory: Desktop OAuth flow helper
"""

import datetime as dt
import json
import os
from dataclasses import asdict, dataclass
from typing import Callable, Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Default scoped permissions requested by CLI and agent setup flows
DEFAULT_GOOGLE_OAUTH_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


# =============================================================================
# Core Dataclasses for Credential Management
# =============================================================================


@dataclass
class UserProviderMetadata:
    """OAuth provider metadata for a specific user from your backend."""

    refresh_token: str
    scope: str  # Space-separated scopes
    expires_at: int  # Unix timestamp
    id_token: Optional[str] = None


@dataclass
class UserInfo:
    """User information from OAuth provider."""

    email: str
    sub: str  # External account ID
    email_verified: bool = True


@dataclass
class CredentialRecord:
    """Structured credential record - dataclass-only API."""

    access_token: str
    user_provider_metadata: UserProviderMetadata
    user_info: UserInfo
    client_id: str
    client_secret: str
    token_uri: str = "https://oauth2.googleapis.com/token"

    @property
    def refresh_token(self) -> str:
        """Get refresh token from provider metadata."""
        return self.user_provider_metadata.refresh_token

    # client_id is now a direct field, no property needed

    @property
    def scopes(self) -> list[str]:
        """Parse scopes from provider metadata."""
        return self.user_provider_metadata.scope.split()

    @property
    def expiry_iso(self) -> str:
        """Get expiry as ISO string."""
        return dt.datetime.fromtimestamp(
            self.user_provider_metadata.expires_at, tz=dt.timezone.utc
        ).isoformat()

    @property
    def user_id(self) -> str:
        """Get user ID (email)."""
        return self.user_info.email

    @property
    def external_account_id(self) -> str:
        """Get external account ID."""
        return self.user_info.sub

    def to_credentials(self) -> Credentials:
        """Convert to google.oauth2.credentials.Credentials object."""
        # Calculate expiry from timestamp - Google auth library expects naive UTC datetime
        expiry = dt.datetime.fromtimestamp(
            self.user_provider_metadata.expires_at, tz=dt.timezone.utc
        ).replace(tzinfo=None)

        creds = Credentials(
            token=self.access_token,
            refresh_token=self.refresh_token,
            id_token=self.user_provider_metadata.id_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=self.scopes,
            expiry=expiry,
        )

        return creds

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "CredentialRecord":
        """Create from dictionary."""
        user_provider_metadata = UserProviderMetadata(**data["user_provider_metadata"])
        user_info = UserInfo(**data["user_info"])

        return cls(
            access_token=data["access_token"],
            user_provider_metadata=user_provider_metadata,
            user_info=user_info,
            client_id=data["client_id"],
            client_secret=data["client_secret"],
            token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        )

    def save_to_file(self, filepath: str) -> None:
        """Save credentials to JSON file."""
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str) -> "CredentialRecord":
        """Load credentials from JSON file."""
        with open(filepath, "r") as f:
            data = json.load(f)
        return cls.from_dict(data)


# =============================================================================
# Desktop OAuth Flow Helpers
# =============================================================================


def desktop_creds_provider_factory(
    credentials_file: str = "credentials.json",
    token_file: str = "token.json",
    scopes: list[str] | None = None,
) -> Callable[[str], Credentials]:
    """
    Returns a creds_provider(user_id) function for desktop OAuth flow.

    Args:
        credentials_file: Path to client secrets JSON
        token_file: Path to store/load access tokens
        scopes: OAuth scopes to request
    """
    if not scopes:
        raise ValueError("scopes parameter is required")

    def _provider(user_id: str) -> Credentials:
        del user_id  # single-user desktop flow; ignore user_id

        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, scopes)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_file, scopes
                )
                creds = flow.run_local_server(port=0)

            # Save updated credentials
            with open(token_file, "w") as f:
                f.write(creds.to_json())

        return creds

    return _provider


def authenticate_user(
    client_id: str,
    client_secret: str,
    scopes: list[str],
    user_storage_path: str,
    credentials_file: str = "credentials.json",
) -> CredentialRecord:
    """
    Authenticate user via browser OAuth and return CredentialRecord.

    Args:
        client_id: Your app's OAuth client ID
        client_secret: Your app's OAuth client secret
        scopes: List of OAuth scopes to request
        user_storage_path: Where to save user credentials
        credentials_file: Path to client secrets JSON
    """
    # Run OAuth flow
    flow = InstalledAppFlow.from_client_secrets_file(credentials_file, scopes)
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    # Decode ID token to get user info
    import base64
    import json as json_lib

    id_token = creds.id_token
    if not id_token:
        raise ValueError("No ID token received - ensure 'openid' scope is included")

    # Simple JWT decode (no verification needed for our use case)
    payload = id_token.split(".")[1]
    # Add padding if needed
    payload += "=" * (4 - len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    user_data = json_lib.loads(decoded)

    granted_scopes = list(creds.scopes or [])

    # Sanity-check that Google returned the requested scopes.
    missing_scopes = [scope for scope in scopes if scope not in granted_scopes]
    if missing_scopes:
        missing = ", ".join(missing_scopes)
        raise RuntimeError(
            "Google OAuth consent did not grant required scopes. "
            f"Missing: {missing}. Re-run setup and ensure you approve the requested permissions."
        )

    # Create structured dataclasses
    user_provider_metadata = UserProviderMetadata(
        refresh_token=creds.refresh_token,
        scope=" ".join(granted_scopes),
        expires_at=int(creds.expiry.timestamp()) if creds.expiry else 0,
        id_token=id_token,
    )

    user_info = UserInfo(
        email=user_data["email"],
        sub=user_data["sub"],
        email_verified=user_data.get("email_verified", True),
    )

    credential_record = CredentialRecord(
        access_token=creds.token,
        user_provider_metadata=user_provider_metadata,
        user_info=user_info,
        client_id=client_id,
        client_secret=client_secret,
    )

    # Save to disk
    credential_record.save_to_file(user_storage_path)

    return credential_record


def load_user_credentials(user_storage_path: str) -> CredentialRecord:
    """Load user credentials from disk."""
    return CredentialRecord.load_from_file(user_storage_path)


# =============================================================================
# Legacy GoogleAccount (for backward compatibility)
# =============================================================================


class GoogleAccount:
    """
    Per-user Google account with credential management and tool shortcuts.
    """

    def __init__(self, user_id: str, source: str, *, desktop=None, records=None):
        self.user_id = user_id
        self.source = source
        self._desktop = desktop or {}
        self._records = records
        self._cache = {}  # key: tuple(scopes) -> Credentials

    @classmethod
    def from_desktop(
        cls, user_id: str, credentials_file="credentials.json", token_file=None
    ):
        """
        Create GoogleAccount for desktop OAuth flow.

        Args:
            user_id: User identifier for token file naming
            credentials_file: Path to client secrets JSON
            token_file: Optional token file path (auto-derived if None)
        """
        # Derive per-user token files if not provided
        return cls(
            user_id,
            "desktop",
            desktop={
                "credentials_file": credentials_file,
                "token_file": token_file or f"token.{user_id}.json",
            },
        )

    @classmethod
    def from_records(cls, user_id: str, records: list[CredentialRecord]):
        """
        Create GoogleAccount from CredentialRecord objects.

        Args:
            user_id: User identifier
            records: List of CredentialRecord objects
        """
        if not isinstance(records, list):
            records = [records]

        # Validate all records are CredentialRecord objects
        for record in records:
            if not isinstance(record, CredentialRecord):
                raise ValueError(f"Expected CredentialRecord, got {type(record)}")

        return cls(user_id, "db", records=records)

    def creds(self, scopes: list[str]) -> Credentials:
        """
        Get Google Credentials for the specified scopes.

        Args:
            scopes: List of OAuth scopes required

        Returns:
            google.oauth2.credentials.Credentials
        """
        key = tuple(sorted(scopes))
        if key in self._cache:
            return self._cache[key]

        if self.source == "desktop":
            provider = desktop_creds_provider_factory(
                credentials_file=self._desktop["credentials_file"],
                token_file=self._desktop["token_file"],
                scopes=scopes,
            )
            creds = provider(self.user_id)
        else:
            creds = self._creds_from_records(scopes)

        self._cache[key] = creds
        return creds

    def _creds_from_records(self, scopes: list[str]) -> Credentials:
        """Build Credentials from CredentialRecord objects."""
        records_list = self._records or []

        # Find the right record for this user
        rec = None
        for r in records_list:
            if r.user_id == self.user_id:
                rec = r
                break

        # Last resort: use first record
        if not rec and records_list:
            rec = records_list[0]

        if not rec:
            raise ValueError("No credential records provided")

        # Use the CredentialRecord's to_credentials method
        return rec.to_credentials()
