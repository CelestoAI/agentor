import json
import logging
import os
import sys
from typing import Any, Dict, List, Literal, Optional

from agentor.tools.base import BaseTool, capability

try:
    from scrapegraph_py import (
        HtmlFormatConfig,
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

logger = logging.getLogger(__name__)

ScrapeFormat = Literal["markdown", "html", "links", "summary"]

_FORMAT_BUILDERS = {
    "markdown": lambda: MarkdownFormatConfig(),
    "html": lambda: HtmlFormatConfig(),
    "links": lambda: LinksFormatConfig(),
    "summary": lambda: SummaryFormatConfig(),
}


def _json_default(data: Any) -> Any:
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    return str(data)


def _serialize(data: Any) -> str:
    if data is None:
        return ""
    return json.dumps(data, default=_json_default)


def _format_result(result: Any, capability_name: str) -> str:
    """Convert an SDK ApiResult into an LLM-friendly string."""
    if getattr(result, "status", None) == "success":
        return _serialize(result.data)
    error = getattr(result, "error", None) or "unknown error"
    return f"Error in {capability_name}: {error}"


class ScrapeGraphAI(BaseTool):
    name = "scrapegraph"
    description = (
        "Scrape the web with ScrapeGraphAI (scrape, extract, search, crawl, monitor)."
    )

    def __init__(self, api_key: Optional[str] = None):
        if _SGAIClient is None:
            if sys.version_info < (3, 12):
                raise ImportError(
                    "ScrapeGraphAI requires Python 3.12 or newer because "
                    "scrapegraph-py 2.x does not support Python 3.10 or 3.11."
                )
            raise ImportError(
                "ScrapeGraphAI dependency is missing. Install it with "
                "`pip install agentor[scrapegraph]`."
            )
        resolved_key = (
            api_key
            or os.environ.get("SGAI_API_KEY")
            or os.environ.get("SCRAPEGRAPH_API_KEY")
        )
        super().__init__(resolved_key)
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
    def stop_crawl(self, crawl_id: str) -> str:
        """Stop a running crawl by id."""
        try:
            result = self.client.crawl.stop(crawl_id)
            return _format_result(result, "stop_crawl")
        except Exception as e:
            logger.exception("ScrapeGraphAI stop_crawl error")
            return f"Error in stop_crawl: {e}"

    @capability
    def resume_crawl(self, crawl_id: str) -> str:
        """Resume a paused crawl by id."""
        try:
            result = self.client.crawl.resume(crawl_id)
            return _format_result(result, "resume_crawl")
        except Exception as e:
            logger.exception("ScrapeGraphAI resume_crawl error")
            return f"Error in resume_crawl: {e}"

    @capability
    def delete_crawl(self, crawl_id: str) -> str:
        """Delete a crawl and its stored results by id."""
        try:
            result = self.client.crawl.delete(crawl_id)
            return _format_result(result, "delete_crawl")
        except Exception as e:
            logger.exception("ScrapeGraphAI delete_crawl error")
            return f"Error in delete_crawl: {e}"

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
    def list_monitors(self) -> str:
        """List all scheduled monitors."""
        try:
            result = self.client.monitor.list()
            return _format_result(result, "list_monitors")
        except Exception as e:
            logger.exception("ScrapeGraphAI list_monitors error")
            return f"Error in list_monitors: {e}"

    @capability
    def get_monitor(self, monitor_id: str) -> str:
        """Fetch a scheduled monitor by id."""
        try:
            result = self.client.monitor.get(monitor_id)
            return _format_result(result, "get_monitor")
        except Exception as e:
            logger.exception("ScrapeGraphAI get_monitor error")
            return f"Error in get_monitor: {e}"

    @capability
    def pause_monitor(self, monitor_id: str) -> str:
        """Pause a scheduled monitor by id."""
        try:
            result = self.client.monitor.pause(monitor_id)
            return _format_result(result, "pause_monitor")
        except Exception as e:
            logger.exception("ScrapeGraphAI pause_monitor error")
            return f"Error in pause_monitor: {e}"

    @capability
    def resume_monitor(self, monitor_id: str) -> str:
        """Resume a paused monitor by id."""
        try:
            result = self.client.monitor.resume(monitor_id)
            return _format_result(result, "resume_monitor")
        except Exception as e:
            logger.exception("ScrapeGraphAI resume_monitor error")
            return f"Error in resume_monitor: {e}"

    @capability
    def delete_monitor(self, monitor_id: str) -> str:
        """Delete a scheduled monitor by id."""
        try:
            result = self.client.monitor.delete(monitor_id)
            return _format_result(result, "delete_monitor")
        except Exception as e:
            logger.exception("ScrapeGraphAI delete_monitor error")
            return f"Error in delete_monitor: {e}"

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
