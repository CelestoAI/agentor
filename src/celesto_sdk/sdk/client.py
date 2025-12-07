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


class CelestoSDK(_BaseConnection):
    """
    Example:
        >> from agentor import CelestoSDK
        >> client = CelestoSDK(CELESTO_API_KEY)
        >> client.toolhub.list_tools()
        >> client.toolhub.run_current_weather_tool("London")
        >> client.deployment.deploy(folder=Path("./my-app"), name="My App", description="Description", envs={})
    """

    def __init__(self, api_key: str, base_url: str = None):
        super().__init__(api_key, base_url)
        self.toolhub = ToolHub(self)
        self.deployment = Deployment(self)
