"""Offline execution tests for the optional deed.page MCP example."""

import json
from types import SimpleNamespace

import pytest
from examples import deed_page

from agentor import Agentor
from agentor.output_text_formatter import AgentOutput, ToolAction
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
    assert result["token"] == "deed_tok_example"
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


def _bind_session(server, session, closed):
    async def connect():
        server._session = session
        return await server.list_tools()

    async def close():
        closed.append(True)
        server._session = None

    server.connect = connect
    server.close = close
    return server


@pytest.mark.asyncio
async def test_publish_tool_reaches_agent_and_result_reaches_model(
    example_connection,
):
    _server, session, closed = example_connection
    captured = []
    server = _bind_session(deed_page.create_agent_server(captured), session, closed)
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
    content = tool_messages[0]["content"]
    assert "quiet-river-a1b2.deed.page" in content
    assert "deed_tok_example" not in content
    assert "token" not in json.loads(content)
    assert captured == [PUBLISHED]
    assert closed == [True]


def _tool_output(name: str, result: str) -> AgentOutput:
    return AgentOutput(
        type="run_item_stream_event",
        message=result,
        tool_action=ToolAction(name=name, type="tool_output"),
    )


def _published(slug: str, token: str | None) -> AgentOutput:
    payload = {"ok": True, "slug": slug, "url": f"https://{slug}.deed.page/"}
    if token:
        payload["token"] = token
    return _tool_output("deed_page_publish_site", json.dumps(payload))


class _Scripted:
    def __init__(self, events):
        self.events = events

    def stream_chat(self, topic, serialize=False, tracing=None):
        events = self.events

        async def generate():
            for event in events:
                yield event

        return generate()


def test_owner_token_is_read_from_the_publish_event(tmp_path, capsys):
    assert not deed_page.handle_stream_event(
        _tool_output("deed_page_publish_site", "Error: RuntimeError: rate limit"),
        tmp_path,
    )
    assert deed_page.handle_stream_event(
        _tool_output("deed_page_publish_site", PUBLISHED), tmp_path
    )
    deed_page.handle_stream_event(
        AgentOutput(
            type="run_item_stream_event",
            message="Published at https://quiet-river-a1b2.deed.page/",
        ),
        tmp_path,
    )

    output = capsys.readouterr().out
    path = tmp_path / "deed-page-owner-quiet-river-a1b2.json"
    assert output.index("Owner token (shown once): deed_tok_example") < output.index(
        "Published at https://quiet-river-a1b2.deed.page/"
    )
    assert "Site URL: https://quiet-river-a1b2.deed.page/" in output
    assert "shown once" in output.lower()
    assert [p.name for p in tmp_path.iterdir()] == [path.name]
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["url"] == "https://quiet-river-a1b2.deed.page/"
    assert saved["token"] == "deed_tok_example"
    assert "shown once" in saved["note"].lower()
    if deed_page.os.name == "posix":
        assert path.stat().st_mode & 0o777 == 0o600


def test_each_site_keeps_its_own_token_file(tmp_path, capsys):
    deed_page.handle_stream_event(
        _published("quiet-river-a1b2", "deed_tok_a"), tmp_path
    )
    deed_page.handle_stream_event(
        _published("bright-harbor-c3d4", "deed_tok_b"), tmp_path
    )
    first = json.loads((tmp_path / "deed-page-owner-quiet-river-a1b2.json").read_text())
    second = json.loads(
        (tmp_path / "deed-page-owner-bright-harbor-c3d4.json").read_text()
    )
    assert first["token"] == "deed_tok_a"
    assert second["token"] == "deed_tok_b"
    assert "deed_tok_a" in capsys.readouterr().out


def test_failed_save_removes_the_temporary_file(tmp_path, monkeypatch):
    def fail_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr(deed_page.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failed"):
        deed_page.handle_stream_event(
            _published("quiet-river-a1b2", "deed_tok_a"), tmp_path
        )
    assert list(tmp_path.iterdir()) == []


def test_redact_publish_result_removes_token_like_fields():
    raw = json.dumps(
        {
            "ok": True,
            "url": "https://quiet-river-a1b2.deed.page/",
            "token": "deed_tok_example",
            "token_note": "Shown once.",
            "owner_token": "deed_tok_owner",
            "nested": {"api_key": "secret-key", "slug": "quiet-river-a1b2"},
        }
    )
    redacted = json.loads(deed_page.redact_publish_result(raw))
    assert redacted["url"] == "https://quiet-river-a1b2.deed.page/"
    assert redacted["token_note"] == "Shown once."
    assert redacted["nested"] == {"slug": "quiet-river-a1b2"}
    assert "deed_tok" not in deed_page.redact_publish_result(raw)
    assert "secret-key" not in deed_page.redact_publish_result(raw)


def test_owner_token_filename_stays_in_the_directory(tmp_path):
    path = deed_page.owner_token_path(
        tmp_path, {"slug": "../secret", "url": "https://x.deed.page/"}
    )
    assert path.parent == tmp_path
    assert path.name == "deed-page-owner-secret.json"


def test_publish_without_a_token_still_prints_the_url(capsys):
    deed_page.handle_stream_event(
        _tool_output(
            "deed_page_publish_site",
            json.dumps({"ok": True, "url": "https://quiet-river-a1b2.deed.page/"}),
        ),
        None,
    )
    output = capsys.readouterr().out
    assert "Site URL: https://quiet-river-a1b2.deed.page/" in output
    assert "No owner token was returned" in output
    assert "deed_tok" not in output


@pytest.mark.asyncio
async def test_missing_or_failed_publish_does_not_invent_a_token(capsys):
    agent = _Scripted(
        [
            _tool_output(
                "deed_page_publish_site", json.dumps({"ok": False, "error": "too big"})
            ),
            _tool_output("other_tool", PUBLISHED),
            _tool_output("deed_page_publish_site", "not json"),
            AgentOutput(
                type="run_item_stream_event", message="I could not publish the page."
            ),
        ]
    )
    await deed_page.follow_publish(agent, "topic", None)
    output = capsys.readouterr().out
    assert "I could not publish the page." in output
    assert "deed.page publish did not succeed; no owner token to show." in output
    assert "deed_tok_example" not in output


@pytest.mark.asyncio
async def test_token_is_saved_before_a_later_model_failure(
    example_connection, tmp_path
):
    _server, session, closed = example_connection
    captured = []
    server = _bind_session(deed_page.create_agent_server(captured), session, closed)
    model = FakeModel(
        calls(
            (
                "deed_page_publish_site",
                json.dumps({"files": {"index.html": "<h1>Report</h1>"}}),
            )
        )
    )
    real_complete = model.complete

    async def fail_after_publish(messages, tools=None, response_format=None):
        if model.calls:
            raise RuntimeError("model down")
        return await real_complete(messages, tools, response_format)

    model.complete = fail_after_publish
    agent = Agentor(name="Publisher", model=model, tools=[server])
    with pytest.raises(RuntimeError, match="model down"):
        await deed_page.follow_publish(agent, "Publish a report", tmp_path, captured)

    saved = json.loads((tmp_path / "deed-page-owner-quiet-river-a1b2.json").read_text())
    assert saved["token"] == "deed_tok_example"
    assert saved["url"] == "https://quiet-river-a1b2.deed.page/"
