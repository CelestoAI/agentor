from rich import print
import asyncio

from agents import function_tool
from agentor import Agentor
from superauth.google import load_user_credentials
from superauth.google import GmailAPI

gmail_api = GmailAPI(load_user_credentials("credentials.my_google_account.json"))


@function_tool
def search_gmail(query: str) -> str:
    """Search Gmail for the given query."""
    return gmail_api.search_messages(query=query, limit=10)


agent = Agentor(
    name="Personal email assistant",
    model="gpt-5-mini",
    tools=[search_gmail],
)


async def main():
    result = await agent.chat(
        "Find emails for maven courses in the last 7 days.",
    )
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
