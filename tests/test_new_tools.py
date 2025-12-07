import unittest
from unittest.mock import MagicMock, patch

from agentor.tools.exa import ExaSearchTool
from agentor.tools.fetch import FetchTool
from agentor.tools.git import GitTool
from agentor.tools.github import GitHubTool
from agentor.tools.postgres import PostgreSQLTool
from agentor.tools.slack import SlackTool


class TestNewTools(unittest.TestCase):
    def setUp(self):
        # Common setup if needed
        pass

    @patch("agentor.tools.exa.Exa")
    def test_exa_search(self, MockExa):
        mock_client = MockExa.return_value
        mock_client.search.return_value = "search results"

        tool = ExaSearchTool(api_key="test")

        # Test capability direct access
        result = tool.search("query")
        self.assertEqual(result, "search results")

        # Test direct method call
        result = tool.search("query")
        self.assertEqual(result, "search results")

        # Test to_openai_function
        tools = tool.to_openai_function()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "search")

    @patch("httpx.Client")
    def test_fetch(self, MockClient):
        mock_client = MockClient.return_value.__enter__.return_value
        mock_client.request.return_value.text = "content"
        mock_client.request.return_value.status_code = 200

        tool = FetchTool()
        result = tool.fetch_url("http://example.com")
        self.assertEqual(result, "content")

        # Test direct method call
        result = tool.fetch_url("http://example.com")
        self.assertEqual(result, "content")

        tools = tool.to_openai_function()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "fetch_url")

    @patch("git.Repo")
    def test_git(self, MockRepo):
        mock_repo = MockRepo.return_value
        mock_repo.git.status.return_value = "On branch main"

        tool = GitTool()
        result = tool.status("/path/to/repo")
        self.assertEqual(result, "On branch main")

        # Test direct method call
        result = tool.status("/path/to/repo")
        self.assertEqual(result, "On branch main")

        tools = tool.to_openai_function()
        self.assertGreaterEqual(len(tools), 4)
        names = [t.name for t in tools]
        self.assertIn("status", names)

    @patch("psycopg2.connect")
    def test_postgres(self, mock_connect):
        mock_conn = mock_connect.return_value
        mock_cur = mock_conn.cursor.return_value
        mock_cur.fetchall.return_value = [("result",)]

        tool = PostgreSQLTool(dsn="postgres://user:pass@host/db")
        result = tool.execute_query("SELECT * FROM table")
        self.assertEqual(result, "[('result',)]")

        # Test direct method call
        result = tool.execute_query("SELECT * FROM table")
        self.assertEqual(result, "[('result',)]")

        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("execute_query", names)

    @patch("agentor.tools.github.PyGithub")
    def test_github(self, MockGithub):
        mock_gh = MockGithub.return_value
        mock_repo = mock_gh.get_repo.return_value
        mock_issue = MagicMock()
        mock_issue.title = "Issue Title"
        mock_issue.body = "Issue Body"
        mock_issue.state = "open"
        mock_repo.get_issue.return_value = mock_issue

        tool = GitHubTool(access_token="test")
        result = tool.get_issue("owner/repo", 1)
        self.assertIn("Issue Title", result)

        # Test direct method call
        result = tool.get_issue("owner/repo", 1)
        self.assertIn("Issue Title", result)

        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("get_issue", names)

    @patch("agentor.tools.slack.WebClient")
    def test_slack(self, MockClient):
        mock_client = MockClient.return_value
        mock_client.chat_postMessage.return_value = {"ts": "1234567890.123456"}

        tool = SlackTool(token="test")
        result = tool.send_message("#general", "Hello")
        self.assertIn("Message sent", result)

        # Test direct method call
        result = tool.send_message("#general", "Hello")
        self.assertIn("Message sent", result)

        tools = tool.to_openai_function()
        names = [t.name for t in tools]
        self.assertIn("send_message", names)


if __name__ == "__main__":
    unittest.main()
