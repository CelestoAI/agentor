"""Connect an agent to a remote MCP server.

The agent connects for the duration of each run and closes afterwards, so the
server can be handed straight to Agentor without a context manager.
"""

import asyncio
import os

from agentor import Agentor
from agentor.mcp import MCPServer

# Replace with your local MCP server URL
mcp_url = "https://api.celesto.ai/v1/mcp-servers/exa"
headers = {
    "Authorization": f"Bearer {os.environ.get('CELESTO_API_KEY')}",
}


async def main() -> None:
    server = MCPServer(url=mcp_url, headers=headers, timeout=10)

    agent = Agentor(
        name="Assistant",
        instructions="You are a helpful assistant with access to a search tool.",
        tools=[server],
    )
    result = await agent.arun("How is the weather in London?")
    print(result.final_output)


asyncio.run(main())
