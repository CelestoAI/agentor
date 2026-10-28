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


def _ok_publish(event) -> dict | None:
    """Parse one successful deed_page_publish_site tool result, if this is one."""
    if event.type != "tool_result" or event.name != "deed_page_publish_site":
        return None
    if event.error or not isinstance(event.result, str):
        return None
    try:
        payload = json.loads(event.result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload.get("ok") or not payload.get("url"):
        return None
    return payload


def successful_publish(events) -> dict | None:
    """Site URL from the latest successful publish, and its one-time owner token.

    The token is returned only on the publish that created the page. A later
    successful call for that same URL may omit it, so the earlier token is kept.
    A token from a different URL is not reused.
    """
    url = None
    token = None
    note = None
    for event in events:
        payload = _ok_publish(event)
        if payload is None:
            continue
        if payload["url"] != url:
            token = None
            note = None
            url = payload["url"]
        raw_token = payload.get("token")
        if isinstance(raw_token, str) and raw_token:
            token = raw_token
            raw_note = payload.get("token_note")
            note = raw_note.strip() if isinstance(raw_note, str) else None
            if note == "":
                note = None
    if url is None:
        return None
    return {"url": url, "token": token, "note": note}


def print_published_site(result, token_path: Path | None = None) -> None:
    """Print the model answer, then the site URL and one-time owner token.

    The token comes from the tool result on ``result.events``, not from the
    model's reply. When a token is present and ``token_path`` is set, it is
    also written there with a note that it is shown once.
    """
    if result.final_output:
        print(result.final_output)

    published = successful_publish(result.events)
    if published is None:
        print("deed.page publish did not succeed; no owner token to show.")
        return

    print(f"Site URL: {published['url']}")
    token = published.get("token")
    if not token:
        print("No owner token was returned. It is shown only on the first publish.")
        return

    note = published.get("note") or (
        "The owner token is shown once. Keep it to update or delete the page."
    )
    print(f"Owner token (shown once): {token}")
    print(note)
    if token_path is None:
        return
    token_path.write_text(
        json.dumps({"url": published["url"], "token": token, "note": note}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    token_path.chmod(0o600)
    print(f"Saved {token_path}. The owner token is shown once.")


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
            "include secrets or private data. Reply with the page URL."
        ),
        tools=[create_server()],
    )
    result = await agent.arun(args.topic)
    print_published_site(result, Path("deed-page-owner.json"))


if __name__ == "__main__":
    asyncio.run(main())
