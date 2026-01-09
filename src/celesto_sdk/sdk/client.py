import json
import os
import tarfile
import tempfile
from pathlib import Path
from typing import List, Optional

import httpx

_BASE_URL = os.environ.get("CELESTO_BASE_URL", "https://api.celesto.ai/v1")


class _BaseConnection:
    def __init__(self, api_key: str, base_url: str = None):
        self.base_url = base_url or _BASE_URL
        if not api_key:
            raise ValueError(
                "API token not found. Log in to https://celesto.ai, navigate to Settings → Security, "
                "and copy your API key to authenticate requests."
            )
        self.api_key = api_key
        self.session = httpx.Client(
            cookies={"access_token": f"Bearer {self.api_key}"},
        )


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


class ToolHub(_BaseClient):
    def list_tools(self) -> List[dict[str, str]]:
        return self.session.get(f"{self.base_url}/toolhub/list").json()

    def run_weather_tool(self, city: str) -> dict:
        return self.session.get(
            f"{self.base_url}/toolhub/current-weather",
            params={"city": city},
        ).json()

    def run_list_google_emails(self, limit: int = 10) -> List[dict[str, str]]:
        return self.session.get(
            f"{self.base_url}/toolhub/list_google_emails", params={"limit": limit}
        ).json()

    def run_send_google_email(
        self, to: str, subject: str, body: str, content_type: str = "text/plain"
    ) -> dict:
        return self.session.post(
            f"{self.base_url}/toolhub/send_google_email",
            {
                "to": to,
                "subject": subject,
                "body": body,
                "content_type": content_type,
            },
        ).json()


class Deployment(_BaseClient):
    def _create_deployment(
        self, bundle: Path, name: str, description: str, envs: dict[str, str]
    ) -> dict:
        if bundle.exists() and not bundle.is_file():
            raise ValueError(f"Bundle {bundle} is not a file")

        # multi part form data where bundle is the file upload
        config = {"env": envs or {}}

        # JSON encode the config since multipart form data doesn't support nested dicts
        data = {
            "name": name,
            "description": description,
            "config": json.dumps(config),
        }

        # Multipart form data with file upload
        with open(bundle, "rb") as f:
            files = {"code_bundle": ("app_bundle.tar.gz", f.read(), "application/gzip")}

            response = self.session.post(
                f"{self.base_url}/deploy/agent",
                files=files,
                data=data,
            )

        if response.status_code not in (200, 201):
            raise Exception(response.text)

        return response.json()

    def deploy(
        self,
        folder: Path,
        name: str,
        description: Optional[str] = None,
        envs: Optional[dict[str, str]] = None,
    ) -> dict:
        if not folder.exists():
            raise ValueError(f"Folder {folder} does not exist")
        if not folder.is_dir():
            raise ValueError(f"Folder {folder} is not a directory")

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
        response = self.session.get(f"{self.base_url}/deploy/apps")
        if response.status_code not in (200, 201):
            raise Exception(response.text)
        return response.json()


class DelegatedAccess(_BaseClient):
    def connect(
        self,
        *,
        subject: str,
        project_name: str,
        provider: str = "google_drive",
        redirect_uri: str | None = None,
    ) -> dict:
        payload: dict[str, str] = {
            "subject": subject,
            "provider": provider,
            "project_name": project_name,
        }
        if redirect_uri:
            payload["redirect_uri"] = redirect_uri

        return self.session.post(
            f"{self.base_url}/delegated-access/connect",
            json=payload,
        ).json()

    def list_connections(
        self,
        *,
        project_name: str,
        status_filter: str | None = None,
    ) -> dict:
        params: dict[str, str] = {"project_name": project_name}
        if status_filter:
            params["status_filter"] = status_filter

        return self.session.get(
            f"{self.base_url}/delegated-access/connections",
            params=params,
        ).json()

    def get_connection(self, connection_id: str) -> dict:
        return self.session.get(
            f"{self.base_url}/delegated-access/connections/{connection_id}",
        ).json()

    def revoke_connection(self, connection_id: str) -> dict:
        return self.session.delete(
            f"{self.base_url}/delegated-access/connections/{connection_id}",
        ).json()

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

        return self.session.get(
            f"{self.base_url}/delegated-access/drive/files",
            params=params,
        ).json()

    # Access Rules Management

    def get_access_rules(self, connection_id: str) -> dict:
        """
        Get access rules for a delegated access connection.

        Args:
            connection_id: The connection ID

        Returns:
            Dict with 'version', 'allowed_folders', 'allowed_files', and 'unrestricted' flag
        """
        return self.session.get(
            f"{self.base_url}/delegated-access/connections/{connection_id}/access-rules",
        ).json()

    def update_access_rules(
        self,
        connection_id: str,
        *,
        allowed_folders: List[str] | None = None,
        allowed_files: List[str] | None = None,
    ) -> dict:
        """
        Update access rules for a delegated access connection.

        Files in allowed_folders (and their subfolders) will be accessible.
        Individual files can be added via allowed_files.
        Setting both to empty lists removes all restrictions.

        Args:
            connection_id: The connection ID
            allowed_folders: List of Google Drive folder IDs with recursive access
            allowed_files: List of individual Google Drive file IDs

        Returns:
            Updated access rules dict
        """
        payload = {
            "allowed_folders": allowed_folders or [],
            "allowed_files": allowed_files or [],
        }
        return self.session.put(
            f"{self.base_url}/delegated-access/connections/{connection_id}/access-rules",
            json=payload,
        ).json()

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
        return self.session.delete(
            f"{self.base_url}/delegated-access/connections/{connection_id}/access-rules",
        ).json()


class CelestoSDK(_BaseConnection):
    """
    Example:
        >> from agentor import CelestoSDK
        >> client = CelestoSDK(CELESTO_API_KEY)
        >> client.toolhub.list_tools()
        >> client.toolhub.run_current_weather_tool("London")
        >> client.deployment.deploy(folder=Path("./my-app"), name="My App", description="Description", envs={})
        >> client.delegated_access.list_connections(project_name="My Project")
    """

    def __init__(self, api_key: str, base_url: str = None):
        super().__init__(api_key, base_url)
        self.toolhub = ToolHub(self)
        self.deployment = Deployment(self)
        self.delegated_access = DelegatedAccess(self)
