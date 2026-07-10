import inspect
import os
import unittest

from agentor.tools import scrapegraphai


class TestScrapeGraphAISDKContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if scrapegraphai._SGAIClient is not None:
            return
        if os.environ.get("AGENTOR_REQUIRE_SCRAPEGRAPH") == "1":
            raise AssertionError(
                "scrapegraph-py v2 must be importable in the SDK contract job"
            )
        raise unittest.SkipTest("scrapegraph-py v2 is not installed")

    def test_sdk_surface_used_by_the_tool(self):
        client = scrapegraphai._SGAIClient(api_key="test-key")
        try:
            expected_methods = {
                client.crawl: ("start", "get", "stop", "resume", "delete"),
                client.monitor: (
                    "create",
                    "list",
                    "get",
                    "pause",
                    "resume",
                    "delete",
                ),
            }
            for resource, method_names in expected_methods.items():
                for method_name in method_names:
                    self.assertTrue(callable(getattr(resource, method_name)))

            self.assertIn("formats", inspect.signature(client.scrape).parameters)
            self.assertIn("schema", inspect.signature(client.extract).parameters)
            self.assertIn("prompt", inspect.signature(client.search).parameters)
        finally:
            client.close()

    def test_format_builders_create_sdk_configs(self):
        for format_name, builder in scrapegraphai._FORMAT_BUILDERS.items():
            config = builder()
            self.assertEqual(config.model_dump(mode="json")["type"], format_name)


if __name__ == "__main__":
    unittest.main()
