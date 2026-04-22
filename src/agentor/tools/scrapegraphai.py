import json
import logging
import os
from typing import Any, Dict, List, Literal, Optional

from agentor.tools.base import BaseTool, capability

try:
    from scrapegraph_py import (
        HtmlFormatConfig,
        JsonFormatConfig,
        LinksFormatConfig,
        MarkdownFormatConfig,
        SummaryFormatConfig,
    )
    from scrapegraph_py import ScrapeGraphAI as _SGAIClient
except ImportError:
    _SGAIClient = None
    MarkdownFormatConfig = None
    HtmlFormatConfig = None
    LinksFormatConfig = None
    SummaryFormatConfig = None
    JsonFormatConfig = None

logger = logging.getLogger(__name__)

ScrapeFormat = Literal["markdown", "html", "links", "summary"]

_FORMAT_BUILDERS = {
    "markdown": lambda: MarkdownFormatConfig(),
    "html": lambda: HtmlFormatConfig(),
    "links": lambda: LinksFormatConfig(),
    "summary": lambda: SummaryFormatConfig(),
}


def _serialize(data: Any) -> str:
    if data is None:
        return ""
    if hasattr(data, "model_dump"):
        data = data.model_dump(mode="json")
    try:
        return json.dumps(data, default=str)
    except TypeError:
        return str(data)


def _format_result(result: Any, capability_name: str) -> str:
    """Convert an SDK ApiResult into an LLM-friendly string."""
    if getattr(result, "status", None) == "success":
        return _serialize(result.data)
    error = getattr(result, "error", None) or "unknown error"
    return f"Error in {capability_name}: {error}"


class ScrapeGraphAI(BaseTool):
    name = "scrapegraph"
    description = "Scrape the web with ScrapeGraphAI (scrape, extract, search, crawl, monitor)."

    def __init__(self, api_key: Optional[str] = None):
        if _SGAIClient is None:
            raise ImportError(
                "ScrapeGraphAI dependency is missing. Please install it with `pip install agentor[scrapegraph]`."
            )
        super().__init__(api_key)
        resolved_key = (
            api_key
            or os.environ.get("SGAI_API_KEY")
            or os.environ.get("SCRAPEGRAPH_API_KEY")
        )
        self.client = _SGAIClient(api_key=resolved_key)

    @capability
    def scrape(self, url: str, format: ScrapeFormat = "markdown") -> str:
        """Fetch a webpage and return its content in the requested format.

        Args:
            url: The URL to scrape.
            format: One of "markdown", "html", "links", "summary". Defaults to markdown.
        """
        try:
            builder = _FORMAT_BUILDERS.get(format)
            if builder is None:
                return (
                    f"Error in scrape: unsupported format '{format}'. "
                    "Use one of: markdown, html, links, summary."
                )
            result = self.client.scrape(url, formats=[builder()])
            return _format_result(result, "scrape")
        except Exception as e:
            logger.exception("ScrapeGraphAI scrape error")
            return f"Error in scrape: {e}"

    @capability
    def extract(
        self,
        prompt: str,
        url: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Extract structured data from a URL using an AI prompt.

        Args:
            prompt: What to extract (e.g. "Extract product names and prices").
            url: The page to extract from.
            schema: Optional JSON schema describing the desired output shape.
        """
        try:
            result = self.client.extract(prompt=prompt, url=url, schema=schema)
            return _format_result(result, "extract")
        except Exception as e:
            logger.exception("ScrapeGraphAI extract error")
            return f"Error in extract: {e}"

    @capability
    def search(
        self,
        query: str,
        num_results: int = 3,
        prompt: Optional[str] = None,
    ) -> str:
        """Search the web and optionally AI-extract from the results.

        Args:
            query: Search query.
            num_results: Number of results to return (1-20).
            prompt: Optional extraction prompt applied to the results.
        """
        try:
            result = self.client.search(query, num_results=num_results, prompt=prompt)
            return _format_result(result, "search")
        except Exception as e:
            logger.exception("ScrapeGraphAI search error")
            return f"Error in search: {e}"

    @capability
    def crawl(
        self,
        url: str,
        max_pages: int = 10,
        max_depth: int = 2,
        include_patterns: Optional[List[str]] = None,
        exclude_patterns: Optional[List[str]] = None,
    ) -> str:
        """Start a crawl job. Returns the crawl id and initial status.

        Args:
            url: Seed URL.
            max_pages: Max pages to crawl.
            max_depth: Max link depth from seed.
            include_patterns: Optional path globs to include (e.g. ["/blog/*"]).
            exclude_patterns: Optional path globs to exclude (e.g. ["/admin/*"]).
        """
        try:
            result = self.client.crawl.start(
                url,
                formats=[MarkdownFormatConfig()],
                max_pages=max_pages,
                max_depth=max_depth,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
            )
            return _format_result(result, "crawl")
        except Exception as e:
            logger.exception("ScrapeGraphAI crawl error")
            return f"Error in crawl: {e}"

    @capability
    def get_crawl_result(self, crawl_id: str) -> str:
        """Fetch the status and results of a crawl by id."""
        try:
            result = self.client.crawl.get(crawl_id)
            return _format_result(result, "get_crawl_result")
        except Exception as e:
            logger.exception("ScrapeGraphAI get_crawl_result error")
            return f"Error in get_crawl_result: {e}"

    @capability
    def monitor(
        self,
        url: str,
        interval: str,
        name: Optional[str] = None,
        webhook_url: Optional[str] = None,
    ) -> str:
        """Create a scheduled monitor for a page.

        Args:
            url: Page to monitor.
            interval: Cron expression, e.g. "0 * * * *" for hourly.
            name: Optional monitor name.
            webhook_url: Optional webhook to receive change notifications.
        """
        try:
            result = self.client.monitor.create(
                url,
                interval,
                name=name,
                formats=[MarkdownFormatConfig()],
                webhook_url=webhook_url,
            )
            return _format_result(result, "monitor")
        except Exception as e:
            logger.exception("ScrapeGraphAI monitor error")
            return f"Error in monitor: {e}"

    @capability
    def credits(self) -> str:
        """Return remaining API credits and plan information."""
        try:
            result = self.client.credits()
            return _format_result(result, "credits")
        except Exception as e:
            logger.exception("ScrapeGraphAI credits error")
            return f"Error in credits: {e}"

    @capability
    def health(self) -> str:
        """Return API health status."""
        try:
            result = self.client.health()
            return _format_result(result, "health")
        except Exception as e:
            logger.exception("ScrapeGraphAI health error")
            return f"Error in health: {e}"
