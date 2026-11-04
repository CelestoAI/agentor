"""Look up repository code through Agentor's MCP client, without a model call.

Setup is in sem_lookup.md.
"""

import argparse
import asyncio
import os

from agentor.mcp import MCPServer


async def lookup(query: str) -> None:
    """Call only sem_find on the operator's local, authenticated Sem server."""
    token = os.environ.get("SEM_MCP_HTTP_TOKEN", "")
    if len(token) < 32:
        raise ValueError("Set SEM_MCP_HTTP_TOKEN to the token used by the Sem server")
    async with MCPServer(
        url="http://127.0.0.1:8787/mcp",
        headers={"Authorization": f"Bearer {token}"},
        name="Sem",
        tool_prefix="repo_",
    ) as server:
        tools = {tool.name: tool for tool in await server.list_tools()}
        if "repo_sem_find" not in tools:
            raise RuntimeError("The server did not advertise sem_find")
        print(await tools["repo_sem_find"].invoke(query=query))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Symbol name to locate in the server's checkout")
    args = parser.parse_args()
    asyncio.run(lookup(args.query))
