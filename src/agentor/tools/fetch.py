from typing import Dict, Optional

import httpx

from agentor.tools.base import BaseTool, capability


class FetchTool(BaseTool):
    name = "fetch"
    description = "Fetch content from a URL using HTTP methods."

    @capability
    def fetch_url(
        self,
        url: str,
        method: str = "GET",
        headers: Optional[Dict[str, str]] = None,
        body: Optional[str] = None,
    ) -> str:
        """
        Fetch content from a URL.

        Args:
            url: The URL to fetch.
            method: The HTTP method to use (GET, POST, PUT, DELETE, etc.).
            headers: Optional headers to include in the request.
            body: Optional body content for POST/PUT requests.
        """
        try:
            with httpx.Client() as client:
                response = client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    timeout=30.0,
                )
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            return f"HTTP Error: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            return f"Error fetching URL: {str(e)}"
