"""Search the web with Agentor's streamable-HTTP MCP client and Keenable.

See keenable_search.md for setup and a mode that needs no model credentials.
"""

import argparse
import asyncio
import os
import uuid

from agentor import Agentor, __version__
from agentor.mcp import MCPServer

PUBLIC_URL = "https://api.keenable.ai/mcp-public"
KEYED_URL = "https://api.keenable.ai/mcp"


def create_server() -> MCPServer:
    """Create a Keenable connection with namespaced tools.

    Without KEENABLE_API_KEY this uses the keyless public endpoint. With a key
    set, it uses the keyed endpoint and sends the key as X-API-Key.
    """
    headers = {"User-Agent": f"agentor/{__version__} (Keenable Search example)"}
    api_key = os.environ.get("KEENABLE_API_KEY")
    if api_key:
        headers["X-API-Key"] = api_key
    return MCPServer(
        url=KEYED_URL if api_key else PUBLIC_URL,
        name="Keenable Search",
        headers=headers,
        tool_prefix="keenable_",
        timeout=30,
    )


async def search_without_model(query: str, fetch_url: str | None = None) -> None:
    """Call the discovered search/fetch tools directly, without an LLM."""
    session_id = str(uuid.uuid4())
    async with create_server() as server:
        tools = {tool.name: tool for tool in await server.list_tools()}
        print(
            await tools["keenable_search_web_pages"].invoke(
                query=query, max_results=5, session_id=session_id
            )
        )
        if fetch_url:
            print(
                await tools["keenable_fetch_page_content"].invoke(
                    url=fetch_url, session_id=session_id
                )
            )


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="Agentor durable agent runs")
    parser.add_argument(
        "--tools-only", action="store_true", help="Search without calling an LLM"
    )
    parser.add_argument("--fetch-url", help="Also fetch a URL in --tools-only mode")
    args = parser.parse_args()
    if args.fetch_url and not args.tools_only:
        parser.error("--fetch-url requires --tools-only")

    if args.tools_only:
        await search_without_model(args.query, args.fetch_url)
        return

    session_id = str(uuid.uuid4())
    agent = Agentor(
        name="Web researcher",
        model="gpt-5-nano",
        instructions=(
            "Use keenable_search_web_pages to research the question and cite source URLs. "
            "Use keenable_fetch_page_content only if the snippets are insufficient. "
            f"Use session_id={session_id} for every search and fetch call. "
            "The configured model_name is gpt-5-nano."
        ),
        tools=[create_server()],
    )
    result = await agent.arun(args.query)
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
