"""Search the web with Agentor's streamable-HTTP MCP client.

See parallel_search.md for setup and a mode that needs no model credentials.
"""

import argparse
import asyncio
import uuid

from agentor import Agentor, __version__
from agentor.mcp import MCPServer


def create_server() -> MCPServer:
    """Create an anonymous Parallel connection with namespaced tools."""
    return MCPServer(
        url="https://search.parallel.ai/mcp",
        name="Parallel Search",
        headers={"User-Agent": f"agentor/{__version__} (Parallel Search example)"},
        tool_prefix="parallel_",
        timeout=30,
    )


async def search_without_model(query: str, fetch_url: str | None = None) -> None:
    """Call the discovered search/fetch tools directly, without an LLM."""
    session_id = str(uuid.uuid4())
    async with create_server() as server:
        tools = {tool.name: tool for tool in await server.list_tools()}
        print(
            await tools["parallel_web_search"].invoke(
                objective=query, search_queries=[query], session_id=session_id
            )
        )
        if fetch_url:
            print(
                await tools["parallel_web_fetch"].invoke(
                    urls=[fetch_url], search_queries=[query], session_id=session_id
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
            "Use parallel_web_search to research the question and cite source URLs. "
            "Use parallel_web_fetch only if the search excerpts are insufficient. "
            f"Use session_id={session_id} for every search and fetch call. "
            "The configured model_name is gpt-5-nano."
        ),
        tools=[create_server()],
    )
    result = await agent.arun(args.query)
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
