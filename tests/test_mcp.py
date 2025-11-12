from agentor import CelestoMCPHub
from agentor.mcp import MCPAPIRouter
from fastapi import Depends
import pytest
from typing import Annotated


@pytest.mark.asyncio
async def test_mcphub():
    mcp_hub = CelestoMCPHub(api_key="test-api-key")
    assert mcp_hub is not None
    assert mcp_hub.mcp_server is not None


@pytest.mark.asyncio
async def test_mcp_router_tool_with_annotation_dep():
    router = MCPAPIRouter()

    async def dependency():
        return {"value": 42, "style": "annotation"}

    @router.tool()
    def sample_tool(
        payload: str, current_user: Annotated[dict[str, object], Depends(dependency)]
    ) -> str:
        assert current_user["style"] == "annotation"
        return f"{payload}-{current_user['value']}"

    response = await router.method_handlers["tools/call"](
        {"params": {"name": "sample_tool", "arguments": {"payload": "ping"}}}
    )

    assert response == {
        "content": [{"type": "text", "text": "ping-42"}],
    }


@pytest.mark.asyncio
async def test_mcp_router_tool_with_default_dep():
    router = MCPAPIRouter()

    class UserService(dict):
        pass

    async def dependency() -> UserService:
        return UserService(value=42, style="default")

    @router.tool()
    def sample_tool(
        payload: str, user_service: UserService = Depends(dependency)
    ) -> str:
        assert isinstance(user_service, UserService)
        assert user_service["style"] == "default"
        return f"{payload}-{user_service['value']}"

    response = await router.method_handlers["tools/call"](
        {"params": {"name": "sample_tool", "arguments": {"payload": "ping"}}}
    )

    assert response == {
        "content": [{"type": "text", "text": "ping-42"}],
    }


@pytest.mark.asyncio
async def test_mcp_router_tool_with_nested_dependencies():
    router = MCPAPIRouter()

    async def get_current_user():
        return {"user_id": "user-123"}

    async def get_org_context(
        current_user: Annotated[dict[str, str], Depends(get_current_user)],
    ):
        return {"org_id": f"org-for-{current_user['user_id']}"}

    @router.tool()
    def sample_tool(context=Depends(get_org_context)):
        return context["org_id"]

    response = await router.method_handlers["tools/call"](
        {"params": {"name": "sample_tool", "arguments": {}}}
    )

    assert response == {
        "content": [
            {"type": "text", "text": "org-for-user-123"},
        ]
    }
