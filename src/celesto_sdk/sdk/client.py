import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import Any, List, Literal, Optional

import httpx

from .exceptions import (
    CelestoAuthenticationError,
    CelestoNetworkError,
    CelestoNotFoundError,
    CelestoRateLimitError,
    CelestoServerError,
    CelestoValidationError,
)

_BASE_URL = os.environ.get("CELESTO_BASE_URL", "https://api.celesto.ai/v1")


class _BaseConnection:
    """Base class providing connection management for Celesto API.

    Handles API key resolution, HTTP session management, and resource cleanup.

    Args:
        api_key: Celesto API key. If not provided, reads from CELESTO_API_KEY
            environment variable.
        base_url: Base URL for the Celesto API. Defaults to https://api.celesto.ai/v1
            or CELESTO_BASE_URL environment variable.

    Raises:
        CelestoAuthenticationError: If no API key is found.

    Example:
        # Explicit API key
        client = CelestoSDK(api_key="your-api-key")

        # From environment variable
        client = CelestoSDK()

        # With context manager for automatic cleanup
        with CelestoSDK() as client:
            deployments = client.deployment.list()
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.base_url = base_url or _BASE_URL

        # Auto-detect API key from environment if not provided
        resolved_api_key = api_key or os.environ.get("CELESTO_API_KEY")
        if not resolved_api_key:
            raise CelestoAuthenticationError(
                "API key not found. Either pass api_key parameter or set the CELESTO_API_KEY "
                "environment variable. Get your API key at https://celesto.ai → Settings → Security."
            )

        self.api_key = resolved_api_key
        self.session = httpx.Client(
            headers={"Authorization": f"Bearer {self.api_key}"},
        )

    def __enter__(self) -> "CelestoSDK":
        """Enter context manager."""
        return self  # type: ignore[return-value]

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager and close resources."""
        self.close()

    def close(self) -> None:
        """Close the HTTP session and release resources.

        Call this method when you're done using the client, or use the
        context manager protocol instead.
        """
        self.session.close()


class _BaseClient:
    def __init__(self, base_connection: _BaseConnection):
        self._base_connection = base_connection

    @property
    def base_url(self):
        return self._base_connection.base_url

    @property
    def api_key(self):
        return self._base_connection.api_key

    @property
    def session(self):
        return self._base_connection.session

    def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        """Make an HTTP request with proper error handling.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            path: URL path (will be joined with base_url)
            params: Query parameters
            json_body: JSON request body
            data: Form data
            files: Files for multipart upload

        Returns:
            Parsed JSON response

        Raises:
            CelestoAuthenticationError: For 401/403 responses
            CelestoNotFoundError: For 404 responses
            CelestoValidationError: For 400/422 responses
            CelestoRateLimitError: For 429 responses
            CelestoServerError: For 5xx responses
            CelestoNetworkError: For connection failures
        """
        url = f"{self.base_url}{path}"

        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                data=data,
                files=files,
            )
        except httpx.ConnectError as e:
            raise CelestoNetworkError(f"Failed to connect to Celesto API: {e}") from e
        except httpx.TimeoutException as e:
            raise CelestoNetworkError(f"Request to Celesto API timed out: {e}") from e
        except httpx.HTTPError as e:
            raise CelestoNetworkError(
                f"Network error while contacting Celesto API: {e}"
            ) from e

        return self._handle_response(response)

    def _handle_response(self, response: httpx.Response) -> Any:
        """Handle HTTP response and raise appropriate exceptions for errors."""
        status = response.status_code

        # Success responses
        if status in (200, 201, 204):
            if status == 204 or not response.content:
                return {}
            try:
                return response.json()
            except json.JSONDecodeError:
                return {"raw_response": response.text}

        # Extract error message from response
        error_message = self._extract_error_message(response)

        # Authentication errors
        if status in (401, 403):
            raise CelestoAuthenticationError(
                f"Authentication failed: {error_message}",
                response=response,
            )

        # Not found
        if status == 404:
            raise CelestoNotFoundError(
                f"Resource not found: {error_message}",
                response=response,
            )

        # Validation errors
        if status in (400, 422):
            raise CelestoValidationError(
                f"Validation error: {error_message}",
                response=response,
            )

        # Rate limiting
        if status == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = (
                int(retry_after) if retry_after and retry_after.isdigit() else None
            )
            raise CelestoRateLimitError(
                f"Rate limit exceeded: {error_message}",
                response=response,
                retry_after=retry_seconds,
            )

        # Server errors
        if status >= 500:
            raise CelestoServerError(
                f"Server error ({status}): {error_message}",
                response=response,
            )

        # Unexpected status code
        raise CelestoServerError(
            f"Unexpected response ({status}): {error_message}",
            response=response,
        )

    def _extract_error_message(self, response: httpx.Response) -> str:
        """Extract error message from response body."""
        try:
            data = response.json()
            # Handle common API error formats
            if isinstance(data, dict):
                return (
                    data.get("error")
                    or data.get("message")
                    or data.get("detail")
                    or str(data)
                )
            return str(data)
        except (json.JSONDecodeError, ValueError):
            return response.text or f"HTTP {response.status_code}"


class Deployment(_BaseClient):
    """Client for deploying agents to Celesto.

    Deploy your AI agents to Celesto's managed infrastructure with automatic
    scaling and monitoring. Agents are packaged and deployed as containerized
    applications.

    Example:
        client = CelestoSDK()

        # Deploy an agent
        result = client.deployment.deploy(
            folder=Path("./my-agent"),
            name="my-agent",
            description="My AI assistant",
            envs={"OPENAI_API_KEY": "sk-..."}
        )
        print(f"Deployment ID: {result['id']}")

        # List all deployments
        deployments = client.deployment.list()
    """

    def _create_deployment(
        self, bundle: Path, name: str, description: str, envs: dict[str, str]
    ) -> dict:
        """Internal method to upload and create a deployment."""
        if bundle.exists() and not bundle.is_file():
            raise CelestoValidationError(f"Bundle {bundle} is not a file")

        # multi part form data where bundle is the file upload
        config = {"env": envs or {}}

        # JSON encode the config since multipart form data doesn't support nested dicts
        form_data = {
            "name": name,
            "description": description,
            "config": json.dumps(config),
        }

        # Multipart form data with file upload
        with open(bundle, "rb") as f:
            files = {"code_bundle": ("app_bundle.tar.gz", f.read(), "application/gzip")}
            return self._request("POST", "/deploy/agent", files=files, data=form_data)

    def deploy(
        self,
        folder: Path,
        name: str,
        description: Optional[str] = None,
        envs: Optional[dict[str, str]] = None,
    ) -> dict:
        """Deploy an agent from a local folder.

        Packages the folder contents into a tar.gz archive and deploys it
        to Celesto. The folder should contain your agent code and any
        configuration files (e.g., requirements.txt, Dockerfile).

        Args:
            folder: Path to the folder containing agent code
            name: Unique name for the deployment
            description: Human-readable description (optional)
            envs: Environment variables to inject (optional)

        Returns:
            Deployment result with 'id', 'status', and other metadata

        Raises:
            CelestoValidationError: If folder doesn't exist or isn't a directory

        Example:
            result = client.deployment.deploy(
                folder=Path("./my-agent"),
                name="weather-bot",
                description="A bot that provides weather information",
                envs={"API_KEY": "secret123"}
            )
            print(f"Status: {result['status']}")  # "READY" or "BUILDING"
        """
        if not folder.exists():
            raise CelestoValidationError(f"Folder {folder} does not exist")
        if not folder.is_dir():
            raise CelestoValidationError(f"Folder {folder} is not a directory")

        # Create tar.gz archive (Nixpacks expects tar.gz format)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".tar.gz") as temp_file:
            with tarfile.open(temp_file.name, "w:gz") as tar:
                for item in folder.iterdir():
                    tar.add(item, arcname=item.name)
            bundle = Path(temp_file.name)

        try:
            return self._create_deployment(bundle, name, description, envs)
        finally:
            bundle.unlink()

    def list(self) -> List[dict]:
        """List all deployments for your account.

        Returns:
            List of deployment objects with id, name, status, etc.

        Example:
            deployments = client.deployment.list()
            for dep in deployments:
                print(f"{dep['name']}: {dep['status']}")
        """
        return self._request("GET", "/deploy/apps")


class GateKeeper(_BaseClient):
    """Client for GateKeeper - delegated access management.

    GateKeeper enables secure delegated access to end-user resources like
    Google Drive. Users authorize access via OAuth, and you can configure
    fine-grained access rules to limit which files/folders are accessible.

    Typical flow:
        1. Call connect() to initiate OAuth for a user
        2. User completes OAuth flow via the returned URL
        3. Configure access rules with update_access_rules()
        4. List files with list_drive_files()

    Example:
        client = CelestoSDK()

        # Initiate connection for a user
        result = client.gatekeeper.connect(
            subject="user:john@example.com",
            project_name="my-project"
        )
        if result.get("oauth_url"):
            print(f"User must authorize: {result['oauth_url']}")

        # After authorization, list their files
        files = client.gatekeeper.list_drive_files(
            project_name="my-project",
            subject="user:john@example.com"
        )
    """

    def connect(
        self,
        *,
        subject: str,
        project_name: str,
        provider: str = "google_drive",
        redirect_uri: str | None = None,
    ) -> dict:
        """Initiate a delegated access connection for a user.

        Creates a new connection or returns an existing one. If the user
        hasn't authorized yet, returns an OAuth URL they must visit.

        Args:
            subject: Unique identifier for the end-user (e.g., "user:email@example.com")
            project_name: Your project name to scope the connection
            provider: OAuth provider (default: "google_drive")
            redirect_uri: Custom OAuth redirect URI (optional)

        Returns:
            Dict with 'connection_id', 'status', and optionally 'oauth_url'
            - status: "pending" (needs OAuth), "authorized", or "failed"
            - oauth_url: Present if user needs to complete OAuth

        Example:
            result = client.gatekeeper.connect(
                subject="user:demo",
                project_name="my-project"
            )
            if oauth_url := result.get("oauth_url"):
                print(f"Please authorize: {oauth_url}")
            elif result["status"] == "authorized":
                print("Already connected!")
        """
        payload: dict[str, str] = {
            "subject": subject,
            "provider": provider,
            "project_name": project_name,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri

        return self._request("POST", "/gatekeeper/connect", json_body=payload)

    def list_connections(
        self,
        *,
        project_name: str,
        status_filter: str | None = None,
    ) -> dict:
        """List all delegated access connections for a project.

        Args:
            project_name: Project name to filter connections
            status_filter: Optional filter by status ("pending", "authorized", "failed")

        Returns:
            Dict with 'connections' list

        Example:
            result = client.gatekeeper.list_connections(
                project_name="my-project",
                status_filter="authorized"
            )
            for conn in result["connections"]:
                print(f"{conn['subject']}: {conn['status']}")
        """
        params: dict[str, str] = {"project_name": project_name}
        if status_filter:
            params["status_filter"] = status_filter

        return self._request("GET", "/gatekeeper/connections", params=params)

    def get_connection(self, connection_id: str) -> dict:
        """Get details of a specific connection.

        Args:
            connection_id: The connection ID

        Returns:
            Connection details including status, subject, provider, etc.

        Raises:
            CelestoNotFoundError: If connection doesn't exist
        """
        return self._request("GET", f"/gatekeeper/connections/{connection_id}")

    def revoke_connection(
        self,
        *,
        subject: str,
        project_name: str,
        provider: str | None = None,
    ) -> dict:
        """Revoke a delegated access connection by subject.

        Finds and revokes the connection for the given subject within the
        specified project. The user will need to re-authorize to regain access.

        Args:
            subject: Subject identifier (e.g., "user:email@example.com")
            project_name: Project name to scope the revocation
            provider: Optional provider filter (e.g., "google_drive")

        Returns:
            Confirmation of revocation with connection ID

        Raises:
            CelestoNotFoundError: If no connection found for the subject

        Example:
            result = client.gatekeeper.revoke_connection(
                subject="user:john@example.com",
                project_name="my-project"
            )
            print(f"Revoked connection: {result['id']}")
        """
        params: dict[str, str] = {
            "subject": subject,
            "project_name": project_name,
        }
        if provider:
            params["provider"] = provider

        return self._request("DELETE", "/gatekeeper/connections", params=params)

    def list_drive_files(
        self,
        *,
        project_name: str,
        subject: str,
        page_size: int = 20,
        page_token: str | None = None,
        folder_id: str | None = None,
        query: str | None = None,
        include_folders: bool = True,
        order_by: str | None = None,
    ) -> dict:
        """
        List Google Drive files for a delegated subject.

        If access rules are configured and no folder_id is specified,
        files from all allowed folders will be returned automatically.
        When access rules are active, a page may contain fewer than page_size
        results after filtering. Use next_page_token to continue.

        Args:
            project_name: Project name to scope the access
            subject: Subject identifier (end-user)
            page_size: Number of files per page (1-1000, default 20)
            page_token: Page token from previous response for pagination
            folder_id: Specific folder ID to list (optional)
            query: Google Drive search query (optional)
            include_folders: Whether to include folders in results
            order_by: Google Drive orderBy parameter (optional)

        Returns:
            Dict with 'files' list and optional 'next_page_token'
        """
        params: dict[str, object] = {
            "project_name": project_name,
            "subject": subject,
            "page_size": page_size,
            "include_folders": include_folders,
        }
        if page_token:
            params["page_token"] = page_token
        if folder_id:
            params["folder_id"] = folder_id
        if query:
            params["query"] = query
        if order_by:
            params["order_by"] = order_by

        return self._request("GET", "/gatekeeper/connectors/drive/files", params=params)

    # Access Rules Management

    def get_access_rules(self, connection_id: str) -> dict:
        """
        Get access rules for a delegated access connection.

        Args:
            connection_id: The connection ID

        Returns:
            Dict with 'version', 'allowed_folders', 'allowed_files', and 'unrestricted' flag
        """
        return self._request(
            "GET", f"/gatekeeper/connections/{connection_id}/access-rules"
        )

    def update_access_rules(
        self,
        *,
        subject: str,
        project_name: str,
        allowed_folders: List[str] | None = None,
        allowed_files: List[str] | None = None,
        provider: str | None = None,
    ) -> dict:
        """
        Update access rules for a delegated access connection by subject.

        Files in allowed_folders (and their subfolders) will be accessible.
        Individual files can be added via allowed_files.
        Setting both to empty lists blocks all access. Use clear_access_rules()
        to remove restrictions.

        Args:
            subject: Subject identifier (e.g., "user:email@example.com")
            project_name: Project name to scope the update
            allowed_folders: List of Google Drive folder IDs with recursive access
            allowed_files: List of individual Google Drive file IDs
            provider: Optional provider filter (e.g., "google_drive")

        Returns:
            Updated access rules dict

        Example:
            result = client.gatekeeper.update_access_rules(
                subject="user:john@example.com",
                project_name="my-project",
                allowed_folders=["folder_id_1", "folder_id_2"],
            )
        """
        params: dict[str, str] = {
            "subject": subject,
            "project_name": project_name,
        }
        if provider:
            params["provider"] = provider

        payload = {
            "allowed_folders": allowed_folders or [],
            "allowed_files": allowed_files or [],
        }
        return self._request(
            "PUT",
            "/gatekeeper/connections/access-rules",
            params=params,
            json_body=payload,
        )

    def clear_access_rules(self, connection_id: str) -> dict:
        """
        Clear access rules for a connection (set to unrestricted).

        This removes all file/folder restrictions, giving the subject
        full access to all files in their Google Drive.

        Args:
            connection_id: The connection ID

        Returns:
            Access rules dict with 'unrestricted': True
        """
        return self._request(
            "DELETE", f"/gatekeeper/connections/{connection_id}/access-rules"
        )


class CelestoSDK(_BaseConnection):
    """Main client for the Celesto AI platform.

    CelestoSDK provides access to all Celesto services through a unified interface:
    - deployment: Deploy and manage AI agents
    - gatekeeper: Manage delegated access to user resources

    The client automatically reads API keys from the CELESTO_API_KEY environment
    variable if not provided explicitly. Use as a context manager for automatic
    resource cleanup.

    Args:
        api_key: Your Celesto API key. If not provided, reads from CELESTO_API_KEY
            environment variable.
        base_url: Custom API base URL (optional, for testing)

    Raises:
        CelestoAuthenticationError: If no API key is found

    Example:
        # Using environment variable (recommended)
        import os
        os.environ["CELESTO_API_KEY"] = "your-api-key"

        with CelestoSDK() as client:
            # Deploy an agent
            result = client.deployment.deploy(
                folder=Path("./my-app"),
                name="My App"
            )

            # Manage delegated access
            connections = client.gatekeeper.list_connections(
                project_name="My Project"
            )
    """

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        super().__init__(api_key, base_url)
        self.deployment = Deployment(self)
        self.gatekeeper = GateKeeper(self)
