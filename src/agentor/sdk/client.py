from typing import List

import httpx


class CelestoSDK:
    _BASE_URL = "https://api.celesto.ai/v1"

    def __init__(self, token: str, base_url: str = None):
        self.base_url = base_url or self._BASE_URL
        if not token:
            raise ValueError("token is required.")

    def list_tools(self) -> List[dict[str, str]]:
        return httpx.get(f"{self.base_url}/toolhub/list").json()
