import os

import pytest
from dotenv import load_dotenv

from agentor import CelestoSDK

load_dotenv(verbose=True)

CELESTO_API_KEY = os.environ.get("CELESTO_API_KEY")


@pytest.fixture()
def client():
    return CelestoSDK(CELESTO_API_KEY, base_url="http://localhost:8500/v1")


@pytest.mark.skipif(not CELESTO_API_KEY, reason="API token not set")
def test_list_tools(client):
    response = client.toolhub.list_tools()
    assert len(response["tools"]) > 1, f"No tools found - {response}"


@pytest.mark.skipif(not CELESTO_API_KEY, reason="API token not set")
def test_current_weather(client):
    response = client.toolhub.run_weather_tool("London")
    assert response["error"] is None, f"error - {response['error']}"
