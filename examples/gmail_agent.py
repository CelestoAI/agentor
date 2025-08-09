from rich import print
from zerozen import agents

prompt = "Find emails for maven courses in the last 7 days."

result = agents.run_sync(
    prompt,
    tools=["search_gmail"],
    user_context={"email_user_id": "me"},
)
print(result)
