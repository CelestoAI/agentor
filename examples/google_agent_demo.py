#!/usr/bin/env python3
"""
Google Agent Desktop Demo

Shows how to use the Google Agent with desktop authentication.
Run desktop_oauth_demo.py first to set up credentials.
"""

import asyncio

from agents import Runner
from rich import print

from agentor.integrations.google.google_agent import build_google_agent_and_context


async def main():
    try:
        # Build agent with desktop credentials
        agent, ctx = build_google_agent_and_context(
            "credentials.my_google_account.json"
        )

        print(f"🤖 Google Agent ready for user: {ctx.user_id}")

        # Example queries to test
        queries = [
            "Find emails for maven courses in the last 7 days.",
            "What meetings do I have today?",
            "Show me unread emails from the last 2 days.",
        ]

        for i, prompt in enumerate(queries, 1):
            print(f"\n📝 Query {i}: {prompt}")
            print("=" * 50)

            result = await Runner.run(
                agent,
                input=prompt,
                context=ctx,
                max_turns=3,
            )

            print(result.final_output)

    except FileNotFoundError as e:
        print("❌ Credentials not found!")
        print("📋 Please run desktop_oauth_demo.py first to authenticate.")
        print(f"   Error: {e}")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
