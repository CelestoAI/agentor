import os
import requests

# When deployed to Celesto (agentor deploy --folder ./examples/agent-server)
# URL = "http://localhost:8500/v1/deploy/apps/APP_ID/chat"
URL = "http://localhost:8000/chat"
CELESTO_API_KEY = os.environ.get("CELESTO_API_KEY")

headers = {
    "Authorization": f"Bearer {CELESTO_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(
    URL,
    json={"input": "What is the weather in London?"},
    stream=True,
    headers=headers,
)
for line in response.iter_lines():
    if line:
        print(line, flush=True)
