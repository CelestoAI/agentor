import os
import requests

# When deployed to Celesto (agentor deploy --folder ./examples/agent-server)
# URL = "https://api.celesto.ai/v1/deploy/apps/my-agent-name/chat"
URL = "http://localhost:8000/chat"
CELESTO_API_KEY = os.environ.get("CELESTO_API_KEY")

headers = {
    "Authorization": f"Bearer {CELESTO_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(
    URL,
    json={"input": "how are you?", "stream": True},
    headers=headers,
    stream=True,
)
for line in response.iter_lines(decode_unicode=True):
    if line:
        print(line, flush=True)
