import unittest
from unittest.mock import MagicMock, patch

from agentor.tools.scrapegraphai import ScrapeGraphAI


class TestScrapeGraphAI(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures."""
        pass

    @patch("agentor.tools.scrapegraphai.Client")
    def test_smartscraper(self, MockClient):
        """Test smartscraper capability."""
        mock_client = MockClient.return_value
        mock_client.smartscraper.return_value = "Extracted content"

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.smartscraper(
            website_url="https://example.com", user_prompt="Extract title"
        )
        self.assertEqual(result, "Extracted content")

        # Test via dispatcher
        result = tool.smartscraper(
            website_url="https://example.com", user_prompt="Extract title"
        )
        self.assertEqual(result, "Extracted content")

        # Test to_openai_function
        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("smartscraper", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_searchscraper(self, MockClient):
        """Test searchscraper capability."""
        mock_client = MockClient.return_value
        mock_client.searchscraper.return_value = "Search results"

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.searchscraper(
            user_prompt="Python tutorials", num_results=3, extraction_mode=True
        )
        self.assertEqual(result, "Search results")

        # Test with default parameters
        result = tool.searchscraper(user_prompt="Python tutorials")
        self.assertEqual(result, "Search results")

        # Test to_openai_function
        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("searchscraper", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_markdownify(self, MockClient):
        """Test markdownify capability."""
        mock_client = MockClient.return_value
        mock_client.markdownify.return_value = "# Title\n\nContent"

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.markdownify(website_url="https://example.com")
        self.assertEqual(result, "# Title\n\nContent")

        # Test via dispatcher
        result = tool.markdownify(website_url="https://example.com")
        self.assertEqual(result, "# Title\n\nContent")

        # Test to_openai_function
        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("markdownify", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_scrape(self, MockClient):
        """Test scrape capability."""
        mock_client = MockClient.return_value
        mock_client.scrape.return_value = "Website content"

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.scrape(website_url="https://example.com")
        self.assertEqual(result, "Website content")

        # Test via dispatcher
        result = tool.scrape(website_url="https://example.com")
        self.assertEqual(result, "Website content")

        # Test to_openai_function
        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("scrape", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_smartcrawler(self, MockClient):
        """Test smartcrawler capability."""
        mock_client = MockClient.return_value
        mock_client.crawl.return_value = "Crawled content"

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.smartcrawler(
            website_url="https://example.com",
            user_prompt="Extract all products",
            max_depth=2,
            max_pages=5,
            sitemap=True,
        )
        self.assertEqual(result, "Crawled content")

        # Test with default parameters
        result = tool.smartcrawler(
            website_url="https://example.com", user_prompt="Extract products"
        )
        self.assertEqual(result, "Crawled content")

        # Test to_openai_function
        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("smartcrawler", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_sitemap(self, MockClient):
        """Test sitemap capability."""
        mock_client = MockClient.return_value
        mock_client.sitemap.return_value = "<?xml version='1.0'?><urlset>...</urlset>"

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.sitemap(website_url="https://example.com")
        self.assertEqual(result, "<?xml version='1.0'?><urlset>...</urlset>")

        # Test via dispatcher
        result = tool.sitemap(website_url="https://example.com")
        self.assertEqual(result, "<?xml version='1.0'?><urlset>...</urlset>")

        # Test to_openai_function
        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("sitemap", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_all_capabilities(self, MockClient):
        """Test that all capabilities are available."""
        mock_client = MockClient.return_value
        mock_client.smartscraper.return_value = "result"
        mock_client.searchscraper.return_value = "result"
        mock_client.markdownify.return_value = "result"
        mock_client.scrape.return_value = "result"
        mock_client.smartcrawler.return_value = "result"
        mock_client.sitemap.return_value = "result"

        tool = ScrapeGraphAI(api_key="test-key")
        tools = tool.to_openai_function()
        names = [t.name for t in tools]

        # Verify all 6 capabilities are present
        self.assertEqual(len(names), 6)
        self.assertIn("smartscraper", names)
        self.assertIn("searchscraper", names)
        self.assertIn("markdownify", names)
        self.assertIn("scrape", names)
        self.assertIn("smartcrawler", names)
        self.assertIn("sitemap", names)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_error_handling(self, MockClient):
        """Test error handling in capabilities."""
        mock_client = MockClient.return_value
        mock_client.smartscraper.side_effect = Exception("API Error")

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.smartscraper(
            website_url="https://example.com", user_prompt="Extract"
        )
        self.assertIn("Error in smartscraper", result)
        self.assertIn("API Error", result)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_error_handling_searchscraper(self, MockClient):
        """Test error handling in searchscraper."""
        mock_client = MockClient.return_value
        mock_client.searchscraper.side_effect = Exception("Search Error")

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.searchscraper(user_prompt="test")
        self.assertIn("Error in searchscraper", result)
        self.assertIn("Search Error", result)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_error_handling_markdownify(self, MockClient):
        """Test error handling in markdownify."""
        mock_client = MockClient.return_value
        mock_client.markdownify.side_effect = Exception("Markdown Error")

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.markdownify(website_url="https://example.com")
        self.assertIn("Error in markdownify", result)
        self.assertIn("Markdown Error", result)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_error_handling_scrape(self, MockClient):
        """Test error handling in scrape."""
        mock_client = MockClient.return_value
        mock_client.scrape.side_effect = Exception("Scrape Error")

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.scrape(website_url="https://example.com")
        self.assertIn("Error in scrape", result)
        self.assertIn("Scrape Error", result)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_error_handling_smartcrawler(self, MockClient):
        """Test error handling in smartcrawler."""
        mock_client = MockClient.return_value
        mock_client.crawl.side_effect = Exception("Crawler Error")

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.smartcrawler(
            website_url="https://example.com", user_prompt="Extract"
        )
        self.assertIn("Error in smartcrawler", result)
        self.assertIn("Crawler Error", result)

    @patch("agentor.tools.scrapegraphai.Client")
    def test_error_handling_sitemap(self, MockClient):
        """Test error handling in sitemap."""
        mock_client = MockClient.return_value
        mock_client.sitemap.side_effect = Exception("Sitemap Error")

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.sitemap(website_url="https://example.com")
        self.assertIn("Error in sitemap", result)
        self.assertIn("Sitemap Error", result)

    @patch("agentor.tools.scrapegraphai.Client", None)
    def test_missing_dependency(self):
        """Test that ImportError is raised when dependency is missing."""
        with self.assertRaises(ImportError) as context:
            ScrapeGraphAI(api_key="test-key")

        self.assertIn(
            "ScrapeGraphAI dependency is missing", str(context.exception)
        )
        self.assertIn(
            "pip install agentor[scrape_graph_ai]", str(context.exception)
        )

    @patch("agentor.tools.scrapegraphai.Client")
    def test_client_initialization(self, MockClient):
        """Test that Client is initialized with API key."""
        ScrapeGraphAI(api_key="test-api-key")
        MockClient.assert_called_once_with(api_key="test-api-key")

    @patch("agentor.tools.scrapegraphai.Client")
    def test_client_initialization_no_api_key(self, MockClient):
        """Test that Client is initialized without API key."""
        ScrapeGraphAI()
        MockClient.assert_called_once_with(api_key=None)


if __name__ == "__main__":
    unittest.main()
