"""Publish an HTML page with Agentor's streamable-HTTP MCP client and deed.page.

See deed_page.md for setup and a mode that needs no model credentials.
"""

import argparse
import asyncio
import json
import os
import tempfile
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


OWNER_NOTE = "The owner token is shown once. Keep it to update or delete the page."


def successful_publish(events) -> dict | None:
    """Last successful deed_page_publish_site payload, or None."""
    found = None
    for event in events:
        if event.type != "tool_result" or event.name != "deed_page_publish_site":
            continue
        if event.error or not isinstance(event.result, str):
            continue
        try:
            payload = json.loads(event.result)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict) and payload.get("ok") and payload.get("url"):
            found = payload
    return found


def owner_token_path(directory: Path, published: dict) -> Path:
    """One private file per site, so a later page does not replace an earlier token."""
    slug = published.get("slug")
    if not isinstance(slug, str) or not slug.strip():
        host = str(published["url"]).split("://", 1)[-1].split("/", 1)[0]
        slug = host.split(".", 1)[0]
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in slug).strip("-")
    return directory / f"deed-page-owner-{safe or 'site'}.json"


def _save_owner_token(path: Path, text: str) -> None:
    """Write the token to a private temporary file, then replace the destination."""
    # mkstemp creates the file as 0600. fchmod is missing on Windows before 3.13.
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    opened = False
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            opened = True
            handle.write(text)
        os.replace(temp_name, path)
    except BaseException:
        if not opened:
            os.close(fd)
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def print_published_site(result, directory: Path | None = None) -> None:
    """Print the model answer, then the site URL and one-time owner token.

    The token comes from the tool result on ``result.events``. When one is
    present and ``directory`` is set, it is saved in that directory under a
    name unique to the site.
    """
    if result.final_output:
        print(result.final_output)

    published = successful_publish(result.events)
    if published is None:
        print("deed.page publish did not succeed; no owner token to show.")
        return

    print(f"Site URL: {published['url']}")
    token = published.get("token")
    if not isinstance(token, str) or not token:
        print("No owner token was returned. It is shown only on the first publish.")
        return

    print(f"Owner token (shown once): {token}")
    print(OWNER_NOTE)
    if directory is None:
        return
    path = owner_token_path(directory, published)
    _save_owner_token(
        path,
        json.dumps(
            {"url": published["url"], "token": token, "note": OWNER_NOTE}, indent=2
        )
        + "\n",
    )
    print(f"Saved {path}. The owner token is shown once.")


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
    print_published_site(result, Path("."))


if __name__ == "__main__":
    asyncio.run(main())
