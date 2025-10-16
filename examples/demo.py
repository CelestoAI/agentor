from rich import print

from agentor import Agentor
from agentor.integrations.google.creds import CredentialRecord
from agentor.integrations.google.gmail_tool import GmailService

gmail_service = GmailService(
    credentials=CredentialRecord.load_from_file(("credentials.my_google_account.json"))
)

agent = Agentor(
    name="Agentor",
    model="gpt-5-mini",
    tools=[gmail_service.search_messages],
)


result = agent.chat(
    "Find emails for maven courses in the last 7 days.",
)
print(result)
