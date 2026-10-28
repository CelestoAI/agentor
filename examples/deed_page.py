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


def _server_kwargs() -> dict:
    return {
        "url": "https://deed.page/mcp",
        "name": "deed.page",
        "headers": {"User-Agent": f"agentor/{__version__} (deed.page example)"},
        "tool_prefix": "deed_page_",
        "timeout": 30,
    }


def create_server() -> MCPServer:
    """Create a keyless deed.page connection with namespaced tools."""
    return MCPServer(**_server_kwargs())


def _token_field(key: str) -> bool:
    """True for an owner token or another credential field name."""
    if not isinstance(key, str):
        return False
    lowered = key.lower().replace("-", "_")
    return (
        lowered == "token"
        or lowered.endswith("_token")
        or lowered
        in {
            "secret",
            "password",
            "api_key",
            "apikey",
        }
    )


def _without_token_fields(value):
    if isinstance(value, dict):
        return {
            key: _without_token_fields(item)
            for key, item in value.items()
            if not _token_field(key)
        }
    if isinstance(value, list):
        return [_without_token_fields(item) for item in value]
    return value


def redact_publish_result(text: str) -> str:
    """Drop owner-token fields from a publish result before it reaches a model."""
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(_without_token_fields(payload))


class _RedactingServer(MCPServer):
    """Same connection, but publish results given to the model omit the token."""

    def __init__(self, captured: list):
        super().__init__(**_server_kwargs())
        self._captured = captured

    def _invoker(self, remote_name: str):
        invoke = super()._invoker(remote_name)
        if remote_name != "publish_site":
            return invoke
        captured = self._captured

        async def invoke_and_redact(**kwargs):
            text = await invoke(**kwargs)
            captured.append(text)
            return redact_publish_result(text)

        return invoke_and_redact


def create_agent_server(captured: list) -> MCPServer:
    """Connection for agent mode. The full publish result is appended to captured."""
    return _RedactingServer(captured)


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


def publish_payload(result: str | None) -> dict | None:
    """Parse one successful deed_page_publish_site tool output, or return None."""
    if not isinstance(result, str):
        return None
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict) or not payload.get("ok") or not payload.get("url"):
        return None
    return payload


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


def print_published_payload(published: dict, directory: Path | None = None) -> None:
    """Print one site URL and owner token, saving the token when it is present."""
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


def _stashed_result(event, captured: list | None, used: set[int]) -> str | None:
    """Full publish text stashed before the model received the redacted copy."""
    if not captured:
        return None
    action = getattr(event, "tool_action", None)
    if (
        action is None
        or action.type != "tool_output"
        or action.name != "deed_page_publish_site"
    ):
        return None
    message = getattr(event, "message", None)
    for index, raw in enumerate(captured):
        if index in used:
            continue
        if redact_publish_result(raw) == message:
            used.add(index)
            return raw
    return None


def handle_stream_event(
    event, directory: Path | None = None, raw_result: str | None = None
) -> bool:
    """Print one stream_chat event. Return True when it published a page.

    ``serialize=False`` yields ``AgentOutput``. A publish is
    ``tool_action.type == "tool_output"`` for ``deed_page_publish_site``.
    The text on ``message`` is what the model sees, which has no owner token.
    ``raw_result`` is the stashed original, used for printing and saving.
    An ordinary message has no tool action and is the model's answer.
    """
    action = getattr(event, "tool_action", None)
    if (
        action is not None
        and action.type == "tool_output"
        and action.name == "deed_page_publish_site"
    ):
        source = (
            raw_result if raw_result is not None else getattr(event, "message", None)
        )
        payload = publish_payload(source)
        if payload is None:
            return False
        print_published_payload(payload, directory)
        return True
    if action is None and getattr(event, "message", None):
        print(event.message)
    return False


async def follow_publish(
    agent, topic: str, directory: Path | None = None, captured: list | None = None
) -> None:
    """Stream the run and record each successful publish as soon as it arrives."""
    used: set[int] = set()
    saw_publish = False
    async for event in agent.stream_chat(topic, serialize=False):
        raw = _stashed_result(event, captured, used)
        if handle_stream_event(event, directory, raw):
            saw_publish = True
    if not saw_publish:
        print("deed.page publish did not succeed; no owner token to show.")


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
    captured: list[str] = []
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
        tools=[create_agent_server(captured)],
    )
    await follow_publish(agent, args.topic, Path("."), captured)


if __name__ == "__main__":
    asyncio.run(main())
