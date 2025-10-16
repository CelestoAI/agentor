from rich import print
import asyncio

from agents import function_tool
from agentor import Agentor
from agentor.integrations.google.creds import CredentialRecord
from agentor.integrations.google.gmail_tool import GmailService

gmail_service = GmailService(
    credentials=CredentialRecord.load_from_file(("credentials.my_google_account.json"))
)


@function_tool
def search_gmail(query: str) -> str:
    """Search Gmail for the given query."""
    return gmail_service.search_messages(query=query, limit=10)


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
