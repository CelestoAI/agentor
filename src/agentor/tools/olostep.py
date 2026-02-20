"""Olostep tool for web scraping, search, AI answers, batch processing, crawling, and site mapping.

Set your API key via the ``OLOSTEP_API_KEY`` environment variable or pass it
directly to the constructor.

Get a free API key at https://olostep.com
"""

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

import httpx

from agentor.tools.base import BaseTool, capability

logger = logging.getLogger(__name__)

OLOSTEP_API_BASE = "https://api.olostep.com/v1"
_DEFAULT_TIMEOUT = 60.0
_POLL_INTERVAL = 5  # seconds between status polls for async jobs


class OlostepTool(BaseTool):
    """Web scraping, search, and AI answers powered by Olostep.

    Provides six capabilities:
    - **scrape**: Extract content from a single URL (markdown, html, json, or text).
    - **search_web**: Structured web search results via the Google Search parser.
    - **answers**: AI-powered web answers with sources and optional JSON output shape.
    - **batch_scrape**: Scrape up to 10 000 URLs in parallel.
    - **crawl**: Autonomously discover and scrape an entire website.
    - **map_website**: Extract all URLs from a website for discovery and analysis.
    """

    name = "olostep"
    description = (
        "Scrape websites, search the web, get AI-powered answers with citations, "
        "batch-scrape URLs, crawl sites, and discover site URLs using Olostep."
    )

    def __init__(self, api_key: Optional[str] = None) -> None:
        super().__init__(api_key)
        self._api_key = api_key or os.environ.get("OLOSTEP_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Olostep API key is required. Pass api_key= or set OLOSTEP_API_KEY."
            )

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

    def _post(self, path: str, payload: Dict[str, Any], timeout: float = _DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """POST to the Olostep REST API and return the JSON response."""
        url = f"{OLOSTEP_API_BASE}/{path.lstrip('/')}"
        with httpx.Client(timeout=timeout) as http:
            response = http.post(url, json=payload, headers=self._headers())
            response.raise_for_status()
            return response.json()

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None, timeout: float = _DEFAULT_TIMEOUT) -> Dict[str, Any]:
        """GET from the Olostep REST API and return the JSON response."""
        url = f"{OLOSTEP_API_BASE}/{path.lstrip('/')}"
        with httpx.Client(timeout=timeout) as http:
            response = http.get(url, params=params, headers=self._headers())
            response.raise_for_status()
            return response.json()

    def _retrieve(self, retrieve_id: str, formats: List[str]) -> Dict[str, Any]:
        """Retrieve previously scraped content by ID."""
        return self._get("retrieve", params={
            "retrieve_id": retrieve_id,
            "formats": ",".join(formats),
        })

    # ------------------------------------------------------------------
    # Capabilities
    # ------------------------------------------------------------------

    @capability
    def scrape(
        self,
        url: str,
        output_format: str = "markdown",
        country: Optional[str] = None,
        wait_before_scraping: int = 0,
        parser: Optional[str] = None,
    ) -> str:
        """Scrape a webpage and return its content.

        Args:
            url: The URL to scrape.
            output_format: Output format - 'markdown', 'html', 'json', or 'text' (default: 'markdown').
            country: Optional country code for geo-targeted scraping (e.g. 'US', 'GB').
            wait_before_scraping: Milliseconds to wait for JS rendering before scraping (0-10000).
            parser: Optional Olostep parser ID for structured extraction (e.g. '@olostep/google-search').
        """
        try:
            payload: Dict[str, Any] = {
                "url_to_scrape": url,
                "formats": [output_format],
            }
            if country:
                payload["country"] = country
            if wait_before_scraping:
                payload["wait_before_scraping"] = wait_before_scraping
            if parser:
                payload["parser"] = {"id": parser}

            data = self._post("scrapes", payload)

            # Return the most relevant content field
            format_key_map = {
                "markdown": "markdown_content",
                "html": "html_content",
                "json": "json_content",
                "text": "text_content",
            }
            key = format_key_map.get(output_format, "markdown_content")
            content = data.get(key)
            if content:
                return json.dumps(content, indent=2) if isinstance(content, (dict, list)) else str(content)

            # Fallback: return entire response
            return json.dumps(data, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("Olostep scrape HTTP error")
            return f"Error scraping URL: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.exception("Olostep scrape error")
            return f"Error scraping URL: {str(e)}"

    @capability
    def search_web(self, query: str, country: str = "US") -> str:
        """Search the web and return structured results (non-AI, parser-based).

        Args:
            query: The search query.
            country: Country code for localized results (default: 'US').
        """
        try:
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"
            payload: Dict[str, Any] = {
                "url_to_scrape": search_url,
                "formats": ["json"],
                "parser": {"id": "@olostep/google-search"},
                "country": country,
            }
            data = self._post("scrapes", payload)

            content = data.get("json_content")
            if content:
                return json.dumps(content, indent=2) if isinstance(content, (dict, list)) else str(content)
            return json.dumps(data, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("Olostep search_web HTTP error")
            return f"Error performing web search: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.exception("Olostep search_web error")
            return f"Error performing web search: {str(e)}"

    @capability
    def answers(
        self,
        task: str,
        output_json_schema: Optional[str] = None,
    ) -> str:
        """Search the web and return an AI-powered answer with sources and citations.

        Args:
            task: A question or task to answer using web data.
            output_json_schema: Optional JSON schema or description of the desired output shape.
        """
        try:
            payload: Dict[str, Any] = {"task": task}
            if output_json_schema:
                payload["json"] = output_json_schema

            data = self._post("answers", payload)
            return json.dumps(data, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("Olostep answers API error")
            return f"Error getting answer: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.exception("Olostep answers error")
            return f"Error getting answer: {str(e)}"

    @capability
    def batch_scrape(
        self,
        urls: List[str],
        output_format: str = "markdown",
        country: Optional[str] = None,
        parser: Optional[str] = None,
    ) -> str:
        """Scrape multiple URLs in parallel (up to 10 000).

        Args:
            urls: List of URLs to scrape.
            output_format: Output format - 'markdown', 'html', 'json', or 'text' (default: 'markdown').
            country: Optional country code for geo-targeted scraping.
            parser: Optional Olostep parser ID for structured extraction.
        """
        try:
            items = [{"url": u, "custom_id": str(i)} for i, u in enumerate(urls)]
            payload: Dict[str, Any] = {"items": items, "formats": [output_format]}
            if country:
                payload["country"] = country
            if parser:
                payload["parser"] = {"id": parser}

            data = self._post("batches", payload)
            batch_id = data.get("batch_id") or data.get("id")

            # Poll until complete
            for _ in range(120):  # max ~10 min
                info = self._get(f"batches/{batch_id}")
                status = info.get("status", "")
                if status in ("completed", "done"):
                    break
                if status in ("failed", "error"):
                    return f"Batch failed: {json.dumps(info, indent=2)}"
                time.sleep(_POLL_INTERVAL)

            # Fetch results
            results_data = self._get(f"batches/{batch_id}/items")
            batch_items = results_data.get("items", results_data.get("data", []))

            format_key = {
                "markdown": "markdown_content",
                "html": "html_content",
                "json": "json_content",
                "text": "text_content",
            }.get(output_format, "markdown_content")

            results = []
            for item in batch_items:
                retrieve_id = item.get("retrieve_id")
                if retrieve_id:
                    content_data = self._retrieve(retrieve_id, [output_format])
                    content = content_data.get(format_key, str(content_data))
                else:
                    content = item.get(format_key, str(item))
                results.append({
                    "url": item.get("url", item.get("custom_id", "unknown")),
                    "content": json.dumps(content, indent=2) if isinstance(content, (dict, list)) else str(content),
                })

            return json.dumps(results, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("Olostep batch_scrape HTTP error")
            return f"Error in batch scrape: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.exception("Olostep batch_scrape error")
            return f"Error in batch scrape: {str(e)}"

    @capability
    def crawl(
        self,
        start_url: str,
        max_pages: int = 25,
        include_urls: Optional[List[str]] = None,
        exclude_urls: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
    ) -> str:
        """Crawl a website by following links from a start URL.

        Args:
            start_url: The URL to begin crawling from.
            max_pages: Maximum number of pages to crawl (default: 25).
            include_urls: URL patterns to include (e.g. ['/blog/**']).
            exclude_urls: URL patterns to exclude (e.g. ['/admin/**']).
            max_depth: Maximum link depth from the start URL.
        """
        try:
            payload: Dict[str, Any] = {
                "start_url": start_url,
                "max_pages": max_pages,
            }
            if include_urls:
                payload["include_urls"] = include_urls
            if exclude_urls:
                payload["exclude_urls"] = exclude_urls
            if max_depth is not None:
                payload["max_depth"] = max_depth

            data = self._post("crawls", payload)
            crawl_id = data.get("crawl_id") or data.get("id")

            # Poll until complete
            for _ in range(120):
                info = self._get(f"crawls/{crawl_id}")
                status = info.get("status", "")
                if status in ("completed", "done"):
                    break
                if status in ("failed", "error"):
                    return f"Crawl failed: {json.dumps(info, indent=2)}"
                time.sleep(_POLL_INTERVAL)

            # Fetch pages
            pages_data = self._get(f"crawls/{crawl_id}/pages")
            pages_list = pages_data.get("pages", pages_data.get("data", []))

            pages = []
            for page in pages_list:
                retrieve_id = page.get("retrieve_id")
                if retrieve_id:
                    content_data = self._retrieve(retrieve_id, ["markdown"])
                    content = content_data.get("markdown_content", str(content_data))
                else:
                    content = page.get("markdown_content", str(page))
                pages.append({
                    "url": page.get("url", "unknown"),
                    "content": str(content),
                })

            return json.dumps(pages, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("Olostep crawl HTTP error")
            return f"Error crawling website: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.exception("Olostep crawl error")
            return f"Error crawling website: {str(e)}"

    @capability
    def map_website(
        self,
        url: str,
        search_query: Optional[str] = None,
        top_n: Optional[int] = None,
        include_urls: Optional[List[str]] = None,
        exclude_urls: Optional[List[str]] = None,
    ) -> str:
        """Discover all URLs on a website, optionally sorted by relevance to a query.

        Args:
            url: The website URL to map.
            search_query: Optional query to sort discovered URLs by relevance.
            top_n: Maximum number of URLs to return.
            include_urls: URL patterns to include (e.g. ['/docs/**']).
            exclude_urls: URL patterns to exclude (e.g. ['/admin/**']).
        """
        try:
            payload: Dict[str, Any] = {"url": url}
            if search_query:
                payload["search_query"] = search_query
            if top_n is not None:
                payload["top_n"] = top_n
            if include_urls:
                payload["include_urls"] = include_urls
            if exclude_urls:
                payload["exclude_urls"] = exclude_urls

            data = self._post("maps", payload)
            urls_found = data.get("urls", [])

            result = {
                "website": url,
                "total_urls": data.get("total_urls", len(urls_found)),
                "urls": urls_found,
            }
            return json.dumps(result, indent=2)
        except httpx.HTTPStatusError as e:
            logger.exception("Olostep map_website HTTP error")
            return f"Error mapping website: {e.response.status_code} - {e.response.text}"
        except Exception as e:
            logger.exception("Olostep map_website error")
            return f"Error mapping website: {str(e)}"
