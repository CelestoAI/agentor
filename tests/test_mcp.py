from agentor import CelestoMCPHub
import pytest


@pytest.mark.asyncio
async def test_mcphub():
    mcp_hub = CelestoMCPHub(api_key="test-api-key")
    assert mcp_hub is not None
    assert mcp_hub.mcp_server is not None
