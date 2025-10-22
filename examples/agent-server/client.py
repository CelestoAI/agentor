import os
import requests

# When deployed to Celesto (agentor deploy --folder ./examples/agent-server)
URL = "https://api.celesto.ai/v1/deploy/apps/d2cdaacb-ee7e-424c-a7e5-42fc260a91d6/chat"
# URL = "http://localhost:8000/chat"
CELESTO_API_KEY = os.environ.get("CELESTO_API_KEY")

headers = {
    "Authorization": f"Bearer {CELESTO_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(
    URL,
    json={"input": "What is the weather in London?"},
    headers=headers,
)
print(response.content)
