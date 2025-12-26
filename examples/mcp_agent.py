import asyncio
import os

from agentor import Agentor
from agentor.mcp import MCPServerStreamableHttp

# Replace with your local MCP server URL
mcp_url = "https://api.celesto.ai/v1/mcp-servers/exa"
headers = {
    "Authorization": f"Bearer {os.environ.get('CELESTO_API_KEY')}",
}


async def main() -> None:
    async with MCPServerStreamableHttp(
        name="Streamable HTTP Python Server",
        params={
            "url": mcp_url,
            "timeout": 10,
            "headers": headers,
        },
        cache_tools_list=True,
        max_retry_attempts=3,
    ) as server:
        agent = Agentor(
            name="Assistant",
            instructions="You are a helpful assistant with access to a search tool.",
            tools=[server],
        )
        result = await agent.arun("How is the weather in London?")
        print(result.final_output)


asyncio.run(main())
