# run_agent.py
import asyncio
from agents import Agent, Runner
from .gmail_tool import GmailTool
from .creds import desktop_creds_provider_factory  # from earlier
import json
from typing import Optional, List
from agents import function_tool, RunContextWrapper

# context.py
from dataclasses import dataclass


@dataclass
class AppContext:
    user_id: str
    gmail: GmailTool


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


SYSTEM_PROMPT = """You are an email search copilot.
Use the `search_gmail` tool with precise Gmail operators (from:, to:, subject:, newer_than:, has:attachment).
Return a short, readable summary of results.
"""


def build_gmail_agent_and_context() -> tuple[Agent, AppContext]:
    # 1) Build creds provider ONCE (desktop or DB-backed)
    creds_provider = desktop_creds_provider_factory(
        credentials_file="credentials.json",
        token_file="token.json",
    )

    # 2) Construct the integration ONCE, inject provider
    gmail = GmailTool(creds_provider)

    # 3) App/Agent context (not visible to the model)
    ctx = AppContext(user_id="local", gmail=gmail)

    # 4) Agent with tool(s)
    agent = Agent(
        name="Mail Agent",
        instructions=SYSTEM_PROMPT,
        tools=[search_gmail],  # tool reads ctx.context.gmail
        model="gpt-4.1-mini",
    )
    return agent, ctx


async def main():
    agent, ctx = build_gmail_agent_and_context()

    result = await Runner.run(
        agent,
        input="Find email from Google in the last 30 days.",
        context=ctx,
        max_turns=3,
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
