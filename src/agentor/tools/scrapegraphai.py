from typing import Optional

from agentor.tools.base import BaseTool, capability

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
except ImportError:
    WebClient = None
    SlackApiError = Exception

import logging

logger = logging.getLogger(__name__)

class ScrapeGraphAI(BaseTool):
    name = "scrape_graphai"
    description = "Scrape a website using GraphAI."

    def __init__(self, api_key: Optional[str] = None):
        if ScrapeGraphAI is None:
            raise ImportError(
                "ScrapeGraphAI dependency is missing. Please install it with `pip install agentor[scrape_graphai]`."
            )
        super().__init__(api_key)
        self.client = ScrapeGraphAI(api_key=api_key)