import requests

# Point this at wherever you are running main.py. The app `agent.serve()` builds
# is a plain FastAPI app with no authentication, so no credentials are needed.
URL = "http://localhost:8000/chat"

response = requests.post(
    URL,
    json={"input": "how are you?"},
    headers={"Content-Type": "application/json"},
    # (connect, read). Without a timeout requests waits forever, and an agent
    # turn that stalls on a model or a tool would hang the client with it.
    timeout=(5, 120),
)
print(response.content.decode("utf-8"))
