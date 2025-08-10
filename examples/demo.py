from rich import print
from zerozen import agents

prompt = "Find emails for maven courses in the last 7 days."

result = agents.run_sync(
    prompt,
    tools=["search_gmail"],
)
print(result)
