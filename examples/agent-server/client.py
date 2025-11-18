import os
import requests
import dotenv

dotenv.load_dotenv()

# When deployed to Celesto (agentor deploy --folder ./examples/agent-server)
URL = "https://api.celesto.ai/v1/deploy/apps/my-agent/chat"
# URL = "http://localhost:8000/chat"
CELESTO_API_KEY = os.environ.get("CELESTO_API_KEY")

headers = {
    "Authorization": f"Bearer {CELESTO_API_KEY}",
    "Content-Type": "application/json",
}

response = requests.post(
    URL,
    json={"input": "how are you?"},
    headers=headers,
)
print(response.content.decode("utf-8"))
