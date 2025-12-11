import json
import os
from unittest.mock import MagicMock, patch

from agentor.tools.linkedin import LinkedInScraperTool


def test_extracts_username_from_linkedin_url():
    tool = LinkedInScraperTool(api_key="key")
    assert (
        tool._extract_username_from_url("https://www.linkedin.com/in/jane-doe/")
        == "jane-doe"
    )
    assert (
        tool._extract_username_from_url("https://linkedin.com/company/example")
        == "example"
    )


@patch("agentor.tools.linkedin.httpx.Client")
def test_scrape_profile_direct_response(mock_client_cls):
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"items": [{"name": "Jane Doe"}]}
    mock_client.post.return_value = mock_response

    tool = LinkedInScraperTool(api_key="api-key", dataset_id="dataset123")
    profile_url = "https://www.linkedin.com/in/jane-doe"
    result = json.loads(tool.scrape_profile(profile_url))

    assert result["status"] == "ok"
    assert result["profile"] == "jane-doe"
    assert result["results"] == [{"name": "Jane Doe"}]
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert "dataset_id=dataset123" in args[0]
    assert kwargs["json"]["input"][0]["url"] == profile_url


@patch("agentor.tools.linkedin.httpx.Client")
def test_scrape_profile_snapshot_response(mock_client_cls):
    mock_client = mock_client_cls.return_value.__enter__.return_value
    mock_response = MagicMock()
    mock_response.status_code = 202
    mock_response.json.return_value = {
        "snapshot_id": "snap-123",
        "created_at": "2024-01-01T00:00:00Z",
    }
    mock_client.post.return_value = mock_response

    tool = LinkedInScraperTool(api_key="api-key", dataset_id="dataset123")
    result = json.loads(tool.scrape_profile("https://www.linkedin.com/in/jane-doe"))

    assert result["status"] == "pending"
    assert result["snapshot_id"] == "snap-123"
    assert "brightdata_response" in result


def test_scrape_profile_missing_api_key():
    with patch.dict(os.environ, {"BRIGHT_DATA_API_KEY": ""}):
        tool = LinkedInScraperTool(api_key=None, dataset_id="dataset123")
    response = tool.scrape_profile("https://www.linkedin.com/in/jane-doe")
    assert "BRIGHT_DATA_API_KEY is required" in response
