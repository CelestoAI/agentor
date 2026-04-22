import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agentor.tools.scrapegraphai import ScrapeGraphAI


def _ok(data):
    return SimpleNamespace(status="success", data=data, error=None, elapsed_ms=1)


def _err(msg):
    return SimpleNamespace(status="error", data=None, error=msg, elapsed_ms=0)


def _build_mock_client():
    """Mock the scrape/extract/search/crawl/monitor/credits/health surface."""
    client = MagicMock()
    client.crawl = MagicMock()
    client.monitor = MagicMock()
    return client


class TestScrapeGraphAI(unittest.TestCase):
    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_scrape_markdown(self, MockClient):
        mock = _build_mock_client()
        mock.scrape.return_value = _ok({"results": {"markdown": {"data": "# Hi"}}})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.scrape(url="https://example.com", format="markdown")
        self.assertIn("# Hi", result)
        # formats arg was passed
        _, kwargs = mock.scrape.call_args
        self.assertIn("formats", kwargs)
        self.assertEqual(len(kwargs["formats"]), 1)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_scrape_unsupported_format(self, MockClient):
        MockClient.return_value = _build_mock_client()
        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.scrape(url="https://example.com", format="bogus")
        self.assertIn("unsupported format", result)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_extract(self, MockClient):
        mock = _build_mock_client()
        mock.extract.return_value = _ok({"products": [{"name": "A", "price": 1}]})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.extract(prompt="extract products", url="https://example.com")
        self.assertIn("products", result)
        mock.extract.assert_called_once_with(
            prompt="extract products", url="https://example.com", schema=None
        )

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_search(self, MockClient):
        mock = _build_mock_client()
        mock.search.return_value = _ok({"results": ["a", "b", "c"]})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.search(query="python tutorials", num_results=3)
        self.assertIn("results", result)
        mock.search.assert_called_once_with(
            "python tutorials", num_results=3, prompt=None
        )

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_crawl(self, MockClient):
        mock = _build_mock_client()
        mock.crawl.start.return_value = _ok({"id": "crawl-123", "status": "queued"})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.crawl(url="https://example.com", max_pages=5, max_depth=2)
        self.assertIn("crawl-123", result)
        _, kwargs = mock.crawl.start.call_args
        self.assertEqual(kwargs["max_pages"], 5)
        self.assertEqual(kwargs["max_depth"], 2)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_get_crawl_result(self, MockClient):
        mock = _build_mock_client()
        mock.crawl.get.return_value = _ok({"id": "crawl-123", "status": "completed"})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.get_crawl_result(crawl_id="crawl-123")
        self.assertIn("completed", result)
        mock.crawl.get.assert_called_once_with("crawl-123")

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_monitor(self, MockClient):
        mock = _build_mock_client()
        mock.monitor.create.return_value = _ok({"id": "mon-1", "status": "active"})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.monitor(url="https://example.com", interval="0 * * * *", name="hourly")
        self.assertIn("mon-1", result)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_credits(self, MockClient):
        mock = _build_mock_client()
        mock.credits.return_value = _ok({"remaining": 100, "used": 10})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.credits()
        self.assertIn("remaining", result)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_health(self, MockClient):
        mock = _build_mock_client()
        mock.health.return_value = _ok({"status": "ok"})
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.health()
        self.assertIn("ok", result)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_error_response_from_api(self, MockClient):
        mock = _build_mock_client()
        mock.scrape.return_value = _err("Invalid or missing API key")
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.scrape(url="https://example.com")
        self.assertIn("Error in scrape", result)
        self.assertIn("Invalid or missing API key", result)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_exception_handling(self, MockClient):
        mock = _build_mock_client()
        mock.extract.side_effect = RuntimeError("boom")
        MockClient.return_value = mock

        tool = ScrapeGraphAI(api_key="test-key")
        result = tool.extract(prompt="p", url="https://example.com")
        self.assertIn("Error in extract", result)
        self.assertIn("boom", result)

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_all_capabilities_registered(self, MockClient):
        MockClient.return_value = _build_mock_client()
        tool = ScrapeGraphAI(api_key="test-key")
        names = [t.name for t in tool.to_openai_function()]
        for expected in [
            "scrape",
            "extract",
            "search",
            "crawl",
            "get_crawl_result",
            "monitor",
            "credits",
            "health",
        ]:
            self.assertIn(expected, names)
        self.assertEqual(len(names), 8)

    @patch("agentor.tools.scrapegraphai._SGAIClient", None)
    def test_missing_dependency(self):
        with self.assertRaises(ImportError) as ctx:
            ScrapeGraphAI(api_key="test-key")
        self.assertIn("ScrapeGraphAI dependency is missing", str(ctx.exception))
        self.assertIn("pip install agentor[scrapegraph]", str(ctx.exception))

    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_client_initialized_with_api_key(self, MockClient):
        MockClient.return_value = _build_mock_client()
        ScrapeGraphAI(api_key="explicit-key")
        MockClient.assert_called_once_with(api_key="explicit-key")

    @patch.dict("os.environ", {"SGAI_API_KEY": "env-key"}, clear=False)
    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_client_initialized_from_env(self, MockClient):
        MockClient.return_value = _build_mock_client()
        ScrapeGraphAI()
        MockClient.assert_called_once_with(api_key="env-key")

    @patch.dict(
        "os.environ",
        {"SCRAPEGRAPH_API_KEY": "legacy-key", "SGAI_API_KEY": ""},
        clear=False,
    )
    @patch("agentor.tools.scrapegraphai._SGAIClient")
    def test_client_honors_legacy_env_var(self, MockClient):
        MockClient.return_value = _build_mock_client()
        ScrapeGraphAI()
        MockClient.assert_called_once_with(api_key="legacy-key")


if __name__ == "__main__":
    unittest.main()
