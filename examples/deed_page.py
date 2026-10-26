"""Publish an HTML page with Agentor's streamable-HTTP MCP client and deed.page.

See deed_page.md for setup and a mode that needs no model credentials.
"""

import argparse
import asyncio
import json
from pathlib import Path

from agentor import Agentor, __version__
from agentor.mcp import MCPServer

SAMPLE_PAGE = (
    "<!doctype html><meta charset='utf-8'><title>Agentor report</title>"
    "<h1>Agentor report</h1><p>Published through Agentor's MCP client.</p>"
)


def create_server() -> MCPServer:
    """Create a keyless deed.page connection with namespaced tools."""
    return MCPServer(
        url="https://deed.page/mcp",
        name="deed.page",
        headers={"User-Agent": f"agentor/{__version__} (deed.page example)"},
        tool_prefix="deed_page_",
        timeout=30,
    )


async def publish_without_model(html: str, ttl_seconds: int) -> dict:
    """Publish one page directly, without an LLM, and return the parsed result."""
    arguments = {"files": {"index.html": html}}
    if ttl_seconds:
        arguments["ttl_seconds"] = ttl_seconds
    async with create_server() as server:
        tools = {tool.name: tool for tool in await server.list_tools()}
        result = json.loads(await tools["deed_page_publish_site"].invoke(**arguments))
    if not result.get("ok"):
        raise RuntimeError(f"deed.page publish failed: {result}")
    return result


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "topic", nargs="?", default="a one-page summary of what Agentor does"
    )
    parser.add_argument(
        "--tools-only", action="store_true", help="Publish without calling an LLM"
    )
    parser.add_argument("--file", type=Path, help="HTML file for --tools-only mode")
    parser.add_argument(
        "--ttl", type=int, default=3600, help="Seconds until expiry; 0 keeps the page"
    )
    args = parser.parse_args()
    if args.file and not args.tools_only:
        parser.error("--file requires --tools-only")
    if args.ttl < 0:
        parser.error("--ttl must be 0 or more")

    if args.tools_only:
        html = args.file.read_text(encoding="utf-8") if args.file else SAMPLE_PAGE
        print(json.dumps(await publish_without_model(html, args.ttl), indent=2))
        return

    expiry = f"Pass ttl_seconds={args.ttl}. " if args.ttl else "Omit ttl_seconds. "
    agent = Agentor(
        name="Page publisher",
        model="gpt-5-nano",
        instructions=(
            "Write a complete, self-contained HTML page about the user's topic and "
            "publish it with deed_page_publish_site, using files={'index.html': ...}. "
            + expiry
            + "Do not call any other deed_page_ tool. The page is public: never "
            "include secrets or private data. Reply with the page URL and the "
            "returned token, which is needed to update or delete the page."
        ),
        tools=[create_server()],
    )
    result = await agent.arun(args.topic)
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
