"""Offline execution tests for the optional deed.page MCP example."""

import json
from types import SimpleNamespace

import pytest
from examples import deed_page

from agentor import Agentor
from agentor.engine.events import Event, RunResult
from tests.test_engine import FakeModel, calls, text
from tests.test_engine_mcp import FakeSession, remote_tool

PUBLISHED = json.dumps(
    {
        "ok": True,
        "slug": "quiet-river-a1b2",
        "url": "https://quiet-river-a1b2.deed.page/",
        "token": "deed_tok_example",
    }
)


@pytest.fixture
def example_connection(monkeypatch):
    server = deed_page.create_server()
    session = FakeSession(
        [remote_tool("publish_site"), remote_tool("delete_site")],
        results={"publish_site": PUBLISHED},
    )
    closed = []

    async def connect():
        server._session = session
        return await server.list_tools()

    async def close():
        closed.append(True)
        server._session = None

    monkeypatch.setattr(server, "connect", connect)
    monkeypatch.setattr(server, "close", close)
    monkeypatch.setattr(deed_page, "create_server", lambda: server)
    return server, session, closed


def test_server_settings():
    server = deed_page.create_server()
    assert server.url == "https://deed.page/mcp"
    assert server.tool_prefix == "deed_page_"
    assert server.headers["User-Agent"].startswith("agentor/")
    assert "Authorization" not in server.headers


@pytest.mark.asyncio
async def test_tools_only_publishes_with_ttl_and_closes(example_connection):
    _server, session, closed = example_connection
    result = await deed_page.publish_without_model("<h1>Hi</h1>", 600)

    assert result["url"] == "https://quiet-river-a1b2.deed.page/"
    assert session.calls == [
        ("publish_site", {"files": {"index.html": "<h1>Hi</h1>"}, "ttl_seconds": 600})
    ]
    assert closed == [True]


@pytest.mark.asyncio
async def test_ttl_zero_omits_expiry(example_connection):
    _server, session, _closed = example_connection
    await deed_page.publish_without_model("<h1>Hi</h1>", 0)
    assert session.calls[0][1] == {"files": {"index.html": "<h1>Hi</h1>"}}


@pytest.mark.asyncio
async def test_tools_only_raises_on_failed_result_and_tool_error(example_connection):
    _server, session, closed = example_connection
    session._results["publish_site"] = json.dumps({"ok": False, "error": "too big"})
    with pytest.raises(RuntimeError, match="too big"):
        await deed_page.publish_without_model("<h1>Hi</h1>", 600)

    async def fail(name, arguments):
        return SimpleNamespace(
            content=[SimpleNamespace(text="Rate limit reached")], is_error=True
        )

    session.call_tool = fail
    with pytest.raises(RuntimeError, match="Rate limit reached"):
        await deed_page.publish_without_model("<h1>Hi</h1>", 600)
    assert closed == [True, True]


@pytest.mark.asyncio
async def test_publish_tool_reaches_agent_and_result_reaches_model(
    example_connection,
):
    server, session, closed = example_connection
    model = FakeModel(
        calls(
            (
                "deed_page_publish_site",
                json.dumps(
                    {"files": {"index.html": "<h1>Report</h1>"}, "ttl_seconds": 3600}
                ),
            )
        ),
        text("Published at https://quiet-river-a1b2.deed.page/"),
    )
    agent = Agentor(name="Publisher", model=model, tools=[server])
    result = await agent.arun("Publish a report")

    assert "quiet-river-a1b2.deed.page" in result.final_output
    assert [name for name, _ in session.calls] == ["publish_site"]
    assert {t["function"]["name"] for t in model.calls[0]["tools"]} == {
        "deed_page_publish_site",
        "deed_page_delete_site",
    }
    tool_messages = [m for m in model.calls[-1]["messages"] if m["role"] == "tool"]
    assert [m["content"] for m in tool_messages] == [PUBLISHED]
    assert closed == [True]


def test_owner_token_is_read_from_the_publish_event(tmp_path, capsys):
    events = [
        Event(
            type="tool_result",
            name="deed_page_publish_site",
            error="RuntimeError: rate limit",
            result="Error: RuntimeError: rate limit",
        ),
        Event(type="tool_result", name="deed_page_publish_site", result=PUBLISHED),
        Event(type="message", text="Published at https://quiet-river-a1b2.deed.page/"),
    ]
    result = RunResult(
        final_output="Published at https://quiet-river-a1b2.deed.page/",
        events=events,
    )
    path = tmp_path / "deed-page-owner.json"
    deed_page.print_published_site(result, path)

    output = capsys.readouterr().out
    assert "Published at https://quiet-river-a1b2.deed.page/" in output
    assert "Site URL: https://quiet-river-a1b2.deed.page/" in output
    assert "Owner token (shown once): deed_tok_example" in output
    assert "shown once" in output.lower()
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["url"] == "https://quiet-river-a1b2.deed.page/"
    assert saved["token"] == "deed_tok_example"
    assert "shown once" in saved["note"].lower()


def test_later_publish_of_the_same_url_keeps_the_one_time_token():
    first = json.dumps(
        {
            "ok": True,
            "url": "https://quiet-river-a1b2.deed.page/",
            "token": "deed_tok_example",
            "token_note": "Shown once. Keep it.",
        }
    )
    second = json.dumps({"ok": True, "url": "https://quiet-river-a1b2.deed.page/"})
    found = deed_page.successful_publish(
        [
            Event(type="tool_result", name="deed_page_publish_site", result=first),
            Event(type="tool_result", name="deed_page_publish_site", result=second),
        ]
    )
    assert found == {
        "url": "https://quiet-river-a1b2.deed.page/",
        "token": "deed_tok_example",
        "note": "Shown once. Keep it.",
    }


def test_token_from_a_different_site_is_not_reused():
    events = [
        Event(
            type="tool_result",
            name="deed_page_publish_site",
            result=json.dumps(
                {"ok": True, "url": "https://a.deed.page/", "token": "deed_tok_a"}
            ),
        ),
        Event(
            type="tool_result",
            name="deed_page_publish_site",
            result=json.dumps({"ok": True, "url": "https://b.deed.page/"}),
        ),
    ]
    assert deed_page.successful_publish(events) == {
        "url": "https://b.deed.page/",
        "token": None,
        "note": None,
    }


def test_publish_without_a_token_still_prints_the_url(capsys):
    result = RunResult(
        final_output="done",
        events=[
            Event(
                type="tool_result",
                name="deed_page_publish_site",
                result=json.dumps(
                    {"ok": True, "url": "https://quiet-river-a1b2.deed.page/"}
                ),
            )
        ],
    )
    deed_page.print_published_site(result, None)
    output = capsys.readouterr().out
    assert "Site URL: https://quiet-river-a1b2.deed.page/" in output
    assert "No owner token was returned" in output
    assert "deed_tok" not in output


def test_missing_or_failed_publish_does_not_invent_a_token(capsys):
    result = RunResult(
        final_output="I could not publish the page.",
        events=[
            Event(
                type="tool_result",
                name="deed_page_publish_site",
                result=json.dumps({"ok": False, "error": "too big"}),
            ),
            Event(
                type="tool_result",
                name="other_tool",
                result=PUBLISHED,
            ),
            Event(
                type="tool_result",
                name="deed_page_publish_site",
                result="not json",
            ),
        ],
    )
    deed_page.print_published_site(result, None)
    output = capsys.readouterr().out
    assert "I could not publish the page." in output
    assert "deed.page publish did not succeed; no owner token to show." in output
    assert "deed_tok_example" not in output
