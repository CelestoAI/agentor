from typing import List

import httpx


class _BaseConnection:
    _BASE_URL = "https://api.celesto.ai/v1"

    def __init__(self, api_key: str, base_url: str = None):
        self.base_url = base_url or self._BASE_URL
        if not api_key:
            raise ValueError("token is required.")


class _BaseClient:
    def __init__(self, base_connection: _BaseConnection):
        self._base_connection = base_connection

    @property
    def base_url(self):
        return self._base_connection.base_url


class ToolHub(_BaseClient):
    def list_tools(self) -> List[dict[str, str]]:
        return httpx.get(f"{self.base_url}/toolhub/list").json()

    def run_weather_tool(self, city: str) -> dict:
        return httpx.get(
            f"{self.base_url}/toolhub/current-weather", params={"city": city}
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
