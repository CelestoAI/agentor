# run_agent.py
import asyncio
from agents import Agent, Runner, ModelSettings
from .gmail_tool import GmailTool
from .calendar_tool import CalendarTool
from .creds import (
    desktop_creds_provider_factory,
    desktop_calendar_creds_provider_factory,
)  # from earlier
import json
from typing import Optional, List
from agents import function_tool, RunContextWrapper
from openai.types.shared import Reasoning

# context.py
from dataclasses import dataclass


@dataclass
class AppContext:
    user_id: str
    gmail: GmailTool
    calendar: CalendarTool


@function_tool(name_override="search_gmail")
async def search_gmail(
    ctx: RunContextWrapper[AppContext],
    query: str,
    label_ids: Optional[List[str]] = None,
    after: Optional[str] = None,  # YYYY-MM-DD or ISO8601
    before: Optional[str] = None,  # YYYY-MM-DD or ISO8601
    limit: int = 20,
) -> str:
    """
    Search Gmail using Gmail query syntax (e.g., `from:alice has:attachment newer_than:7d`).
    Returns a compact list of message summaries.

    Args:
        query: Gmail search string.
        label_ids: Optional Gmail label IDs to filter by.
        after: Lower bound date (inclusive).
        before: Upper bound date (exclusive).
        limit: Max results (1-50).
    """
    app = ctx.context
    res = app.gmail.search_messages(
        user_id=app.user_id,
        query=query,
        label_ids=label_ids,
        after=after,
        before=before,
        limit=limit,
    )
    # Tool outputs must be strings; agent will get this as the tool result.
    return json.dumps(res)


@function_tool(name_override="list_gmail_messages")
async def list_gmail_messages(
    ctx: RunContextWrapper[AppContext],
    label_ids: Optional[List[str]] = None,
    q: Optional[str] = None,
    limit: int = 20,
    page_token: Optional[str] = None,
    include_spam_trash: bool = False,
) -> str:
    """
    List message IDs using Gmail's list API (fast, minimal data).

    Args:
        label_ids: Filter by label IDs.
        q: Optional Gmail query string.
        limit: Max results (1-100).
        page_token: For pagination.
        include_spam_trash: Whether to include spam and trash.
    """
    app = ctx.context
    res = app.gmail.list_messages(
        user_id=app.user_id,
        label_ids=label_ids,
        q=q,
        limit=limit,
        page_token=page_token,
        include_spam_trash=include_spam_trash,
    )
    return json.dumps(res)


@function_tool(name_override="get_gmail_message")
async def get_gmail_message(
    ctx: RunContextWrapper[AppContext],
    message_id: str,
) -> str:
    """
    Fetch a single Gmail message (metadata only).

    Args:
        message_id: Gmail message ID.
    """
    app = ctx.context
    res = app.gmail.get_message(
        user_id=app.user_id,
        message_id=message_id,
    )
    return json.dumps(res)


@function_tool(name_override="get_gmail_message_body")
async def get_gmail_message_body(
    ctx: RunContextWrapper[AppContext],
    message_id: str,
    prefer: str = "text",
    limit: int = 50000,
) -> str:
    """
    Fetch a single Gmail message body for UI rendering.

    Args:
        message_id: Gmail message ID.
        prefer: "text" or "html". Defaults to "text".
        limit: Max characters to return for the selected body.
    """
    app = ctx.context
    data = app.gmail.get_message_body(
        user_id=app.user_id, message_id=message_id, prefer=prefer, max_chars=limit
    )
    return json.dumps(data)


@function_tool(name_override="list_calendar_events")
async def list_calendar_events(
    ctx: RunContextWrapper[AppContext],
    calendar_id: str = "primary",
    time_min: Optional[str] = None,  # YYYY-MM-DD or RFC3339
    time_max: Optional[str] = None,  # YYYY-MM-DD or RFC3339
    max_results: int = 50,
    page_token: Optional[str] = None,
) -> str:
    """
    List Google Calendar events.
    """
    app = ctx.context
    res = app.calendar.list_events(
        user_id=app.user_id,
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        page_token=page_token,
    )
    return json.dumps(res)


@function_tool(name_override="get_calendar_event")
async def get_calendar_event(
    ctx: RunContextWrapper[AppContext],
    event_id: str,
    calendar_id: str = "primary",
) -> str:
    """
    Get a single Google Calendar event.
    """
    app = ctx.context
    res = app.calendar.get_event(
        user_id=app.user_id, calendar_id=calendar_id, event_id=event_id
    )
    return json.dumps(res)


SYSTEM_PROMPT = """
You are a READ-ONLY Gmail + Google Calendar subagent invoked by a parent orchestrator.
Do NOT converse with the end user. Produce concise, structured outputs for the parent.

# Scope & contract
- Scope: retrieval/summarization only. No sending, deleting, modifying, or scheduling actions.
- Audience: the parent agent. Never ask the user questions directly.
- If more info is needed, return a CLARIFICATION block with fields the parent can ask the user.

# Operating principles
- Smallest sufficient tool call(s). Prefer narrow queries over broad listings.
- Metadata-first for Gmail; fetch full bodies ONLY when the parent explicitly requests reading/quoting content.
- Minimize data: use limits (10 by default, up to 20 if necessary). Use page_token for more.
- Never fabricate results. If nothing is found, return an empty RESULTS list with reason.
- Respect privacy: quote only relevant passages from bodies when requested.

# Tools
GMAIL
- search_gmail(query, limit=10..20, page_token)
  Supported operators: from:, to:, subject:, label:, has:attachment, is:unread, newer_than:, older_than:, after:, before:
- list_gmail_messages(label_ids=None, limit=10..20, page_token)
- get_gmail_message(id)  # headers/snippet/metadata
- get_gmail_message_body(id, prefer_text=True)  # ONLY if explicitly asked to read

CALENDAR
- list_calendar_events(time_min, time_max, max_results=10, calendar_id="primary", page_token)
- get_calendar_event(event_id)

# Date & time
- Resolve vague ranges to concrete operators/ISO:
  - “last N days” → newer_than:Nd (Gmail)
  - “this week/next week/last week” → ISO date ranges (Calendar)
  - Weekday refs (“next Tuesday”) → concrete date(s).
- Output times in ISO8601 with timezone (e.g., 2025-08-09T13:30:00+01:00).

# Output format (parent-facing; JSON-ish text)
Return one of the following top-level envelopes:

OK
- Use when work completed successfully.
- Structure:
  STATUS: "OK"
  RESULTS: [
    # Gmail item
    { "type":"gmail",
      "id": "<msg_id>",
      "from": "<name/email>",
      "subject": "<subject>",
      "date": "<ISO8601>",
      "snippet": "<short snippet>",
      "labelIds": ["..."]
    },
    # Calendar item
    { "type":"calendar",
      "event_id":"<id>",
      "title":"<title>",
      "start":"<ISO8601>",
      "end":"<ISO8601>",
      "location":"<loc or None>",
      "conference":"<meet/zoom or None>"
    }
  ]
  PAGINATION: { "page_token": "<token or null>" }
  NOTES: "<1–2 line helpful note or null>"

READ_CONTENT
- Use only if the parent asked to read/quote a specific email.
- Structure:
  STATUS: "READ_CONTENT"
  MESSAGE_ID: "<msg_id>"
  EXCERPT: "<targeted excerpt or brief bullet summary>"
  SAFETY: "sensitive|non-sensitive"
  NOTES: "<context or null>"

CLARIFICATION
- Use when you cannot proceed safely/accurately without missing info.
- Structure:
  STATUS: "CLARIFICATION"
  NEEDS: [
    { "field":"sender|subject|time_range|label|event_title|date", "why":"<short reason>", "examples":"<optional>" }
  ]
  SUGGESTED_QUERIES: ["<narrow query 1>", "<narrow query 2>"]

ERROR
- Use on tool failure or unexpected response.
- Structure:
  STATUS: "ERROR"
  ERROR_TYPE: "tool_error|invalid_params|rate_limited|not_found|unknown"
  MESSAGE: "<short description>"
  RETRYABLE: true|false

# Decision guide
1) If user intent maps to Gmail filters → prefer search_gmail.
2) If only counts/IDs/quick overview → list_gmail_messages (or search + get_gmail_message for minimal fields).
3) Only call get_gmail_message_body when parent explicitly asks to read/open/quote content.
4) For Calendar ranges → list_calendar_events with explicit time_min/time_max.
5) For a known event → get_calendar_event.
6) If ambiguous → return CLARIFICATION (do not guess).

# Defaults & constraints
- Gmail limit=10 (≤20 if needed). Calendar max_results=10.
- Always include PAGINATION.page_token when present from the tool.
- Summaries should be brief; do not include entire bodies unless requested.
- Never follow links or process attachments.

# Examples (parent intent → actions → output)
- Intent: “Find email from Google in last 30 days (metadata only)”
  → search_gmail(query="from:google newer_than:30d", limit=10)
  → Output: STATUS=OK with Gmail RESULTS, PAGINATION token if any.

- Intent: “Open the latest message from HR and summarize”
  → search_gmail("from:hr@company.com", limit=1) → get_gmail_message(id) → get_gmail_message_body(id)
  → Output: STATUS=READ_CONTENT with EXCERPT + SAFETY classification.

- Intent: “Meetings this week”
  → list_calendar_events(time_min=<ISO Monday 00:00>, time_max=<ISO Sunday 23:59>, max_results=10)
  → Output: STATUS=OK with Calendar RESULTS.

# Style
- Be terse, structured, and deterministic.
- No user-directed phrasing. Write for the orchestrator.
- Include timezone in all datetimes.
"""


def build_google_agent_and_context() -> tuple[Agent, AppContext]:
    # 1) Build creds provider ONCE (desktop or DB-backed)
    creds_provider = desktop_creds_provider_factory(
        credentials_file="credentials.json",
        token_file="token.json",
    )
    cal_creds_provider = desktop_calendar_creds_provider_factory(
        credentials_file="credentials.json",
        token_file="token.calendar.json",
    )

    # 2) Construct the integration ONCE, inject provider
    gmail = GmailTool(creds_provider)
    calendar = CalendarTool(cal_creds_provider)

    # 3) App/Agent context (not visible to the model)
    ctx = AppContext(user_id="local", gmail=gmail, calendar=calendar)

    # 4) Agent with tool(s)
    agent = Agent(
        name="Google Apps Agent",
        instructions=SYSTEM_PROMPT,
        tools=[
            search_gmail,
            list_gmail_messages,
            get_gmail_message,
            get_gmail_message_body,
            list_calendar_events,
            get_calendar_event,
        ],  # tool reads ctx.context.gmail
        model="gpt-5",
        model_settings=ModelSettings(
            reasoning=Reasoning(
                effort="low",
            )
        ),
    )
    return agent, ctx


async def main():
    agent, ctx = build_google_agent_and_context()

    result = await Runner.run(
        agent,
        input="Find email from Google in the last 30 days.",
        context=ctx,
        max_turns=3,
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
