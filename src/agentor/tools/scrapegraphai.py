from typing import Optional, Dict, Any

from agentor.tools.base import BaseTool, capability

try:
    from scrapegraph_py import Client
except ImportError:
    Client = None

import logging

logger = logging.getLogger(__name__)


class ScrapeGraphAI(BaseTool):
    name = "scrape_graph_ai"
    description = "Scrape websites using ScrapeGraphAI."

    def __init__(self, api_key: Optional[str] = None):
        if Client is None:
            raise ImportError(
                "ScrapeGraphAI dependency is missing. Please install it with `pip install agentor[scrape_graph_ai]`."
            )
        super().__init__(api_key)
        self.client = Client(api_key=api_key)

    @capability
    def smartscraper(self, website_url: str, user_prompt: str) -> str:
        """Extract information from a website using AI-powered smart scraping."""
        try:
            response = self.client.smartscraper(
                website_url=website_url,
                user_prompt=user_prompt
            )
            return str(response)
        except Exception as e:
            logger.exception("ScrapeGraphAI SmartScraper Error")
            return f"Error in smartscraper: {str(e)}"

    @capability
    def searchscraper(self, user_prompt: str, num_results: int = 3, extraction_mode: bool = True) -> str:
        """Search and extract information using AI-powered search scraping."""
        try:
            response = self.client.searchscraper(
                user_prompt=user_prompt,
                num_results=num_results,
                extraction_mode=extraction_mode
            )
            return str(response)
        except Exception as e:
            logger.exception("ScrapeGraphAI SearchScraper Error")
            return f"Error in searchscraper: {str(e)}"

    @capability
    def markdownify(self, website_url: str) -> str:
        """Convert a website to markdown format."""
        try:
            response = self.client.markdownify(
                website_url=website_url
            )
            return str(response)
        except Exception as e:
            logger.exception("ScrapeGraphAI Markdownify Error")
            return f"Error in markdownify: {str(e)}"

    @capability
    def scrape(self, website_url: str) -> str:
        """Scrape a website and return its content."""
        try:
            response = self.client.scrape(
                website_url=website_url
            )
            return str(response)
        except Exception as e:
            logger.exception("ScrapeGraphAI Scrape Error")
            return f"Error in scrape: {str(e)}"

    @capability
    def smartcrawler(
        self,
        website_url: str,
        user_prompt: str,
        max_depth: int = 1,
        max_pages: int = 3,
        sitemap: bool = True,
        extraction_mode: bool = False,
        data_schema: Optional[Dict[str, Any]] = None
    ) -> str:
        """Crawl a website intelligently using AI to extract data across multiple pages.
        
        Args:
            website_url: The URL of the website to crawl
            user_prompt: Prompt describing what to extract (used when extraction_mode=True)
            max_depth: Maximum depth of crawling (default: 1)
            max_pages: Maximum number of pages to crawl (default: 3)
            sitemap: Whether to use sitemap for crawling (default: True)
            extraction_mode: Whether to use extraction mode (requires data_schema if True, default: False)
            data_schema: Data schema for extraction (required if extraction_mode=True)
        """
        try:
            crawl_params = {
                "url": website_url,
                "depth": max_depth,
                "max_pages": max_pages,
                "sitemap": sitemap,
                "extraction_mode": extraction_mode
            }
            
            # Include prompt and data_schema only when extraction_mode=True
            if extraction_mode:
                if data_schema is None:
                    raise ValueError("data_schema is required when extraction_mode=True")
                crawl_params["prompt"] = user_prompt
                crawl_params["data_schema"] = data_schema
            response = self.client.crawl(**crawl_params)
            return str(response)
        except Exception as e:
            logger.exception("ScrapeGraphAI SmartCrawler Error")
            return f"Error in smartcrawler: {str(e)}"

    @capability
    def sitemap(self, website_url: str) -> str:
        """Get the sitemap of a website."""
        try:
            response = self.client.sitemap(
                website_url=website_url
            )
            return str(response)
        except Exception as e:
            logger.exception("ScrapeGraphAI Sitemap Error")
            return f"Error in sitemap: {str(e)}"
