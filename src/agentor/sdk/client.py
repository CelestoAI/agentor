from typing import List

import httpx


class _BaseConnection:
    _BASE_URL = "https://api.celesto.ai/v1"

    def __init__(self, api_key: str, base_url: str = None):
        self.base_url = base_url or self._BASE_URL
        if not api_key:
            raise ValueError("token is required.")
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


class CelestoSDK(_BaseConnection):
    """
    Example:
        >> from agentor import CelestoSDK
        >> client = CelestoSDK(CELESTO_API_KEY)
        >> client.toolhub.list_tools()
        >> client.toolhub.run_current_weather_tool("London")
    """

    def __init__(self, api_key: str, base_url: str = None):
        super().__init__(api_key, base_url)
        self.toolhub = ToolHub(self)
