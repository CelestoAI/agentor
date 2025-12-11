import json
import os
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import httpx

from agentor.tools.base import BaseTool, capability


class LinkedInScraperTool(BaseTool):
    name = "linkedin_scraper"
    description = "Scrape LinkedIn profile data using Bright Data datasets."

    def __init__(self, api_key: Optional[str] = None, dataset_id: Optional[str] = None):
        """
        Initialize the LinkedIn scraper.

        Args:
            api_key: Bright Data API key. Defaults to BRIGHT_DATA_API_KEY env var.
            dataset_id: Bright Data dataset ID. Defaults to BRIGHT_DATA_DATASET_ID or
                a maintained fallback dataset.
        """
        super().__init__(api_key or os.environ.get("BRIGHT_DATA_API_KEY"))
        self.dataset_id = dataset_id or os.environ.get(
            "BRIGHT_DATA_DATASET_ID", "gd_l1viktl72bvl7bjuj0"
        )

    def _extract_username_from_url(self, linkedin_url: str) -> str:
        """Extract the username slug from a LinkedIn profile URL."""
        parsed_url = urlparse(linkedin_url)
        path_parts = parsed_url.path.strip("/").split("/")

        if "in" in path_parts:
            username_index = path_parts.index("in") + 1
            if username_index < len(path_parts):
                username = path_parts[username_index]
                username = username.split("?")[0].split("#")[0]
                return username.strip("/")

        if path_parts:
            username = path_parts[-1].split("?")[0].split("#")[0].strip("/")
            return username if username else "unknown"

        return "unknown"

    @capability
    def scrape_profile(self, linkedin_url: str, force_refresh: bool = False) -> str:
        """
        Scrape a LinkedIn profile using Bright Data datasets.

        Args:
            linkedin_url: The LinkedIn profile URL to scrape.
            force_refresh: Unused flag retained for API compatibility.
        """
        _ = force_refresh

        if not linkedin_url:
            return "Error: LinkedIn profile URL is required."

        username = self._extract_username_from_url(linkedin_url)
        if not username or username == "unknown":
            return "Error: Could not extract LinkedIn username from the provided URL."

        if not self.api_key:
            return "Error: BRIGHT_DATA_API_KEY is required to use the LinkedIn scraper."

        api_url = (
            "https://api.brightdata.com/datasets/v3/scrape"
            f"?dataset_id={self.dataset_id}&notify=false&include_errors=true"
        )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {"input": [{"url": linkedin_url}]}

        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(api_url, headers=headers, json=payload)
        except Exception as exc:
            return f"Error contacting Bright Data: {exc}"

        if response.status_code not in (200, 202):
            try:
                error_details = response.text
            except Exception:
                error_details = ""
            return (
                f"Error: Bright Data returned status {response.status_code}. "
                f"{error_details}".strip()
            )

        try:
            response_data = response.json()
        except Exception as exc:
            return f"Error: Failed to parse Bright Data response: {exc}"

        result: Dict[str, Any] = {
            "status": "ok",
            "profile": username,
            "url": linkedin_url,
        }

        if isinstance(response_data, Dict) and "snapshot_id" in response_data:
            result.update(
                {
                    "status": "pending",
                    "snapshot_id": response_data["snapshot_id"],
                    "requested_at": response_data.get("created_at"),
                    "message": "Snapshot created. Poll Bright Data for results.",
                    "brightdata_response": response_data,
                }
            )
            return json.dumps(result)

        if isinstance(response_data, Dict) and "items" in response_data:
            result["results"] = response_data["items"]
        else:
            result["results"] = response_data

        return json.dumps(result)
