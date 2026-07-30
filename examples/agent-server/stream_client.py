import requests

# Point this at wherever you are running main.py. The app `agent.serve()` builds
# is a plain FastAPI app with no authentication, so no credentials are needed.
URL = "http://localhost:8000/chat"

response = requests.post(
    URL,
    json={"input": "how are you?", "stream": True},
    headers={"Content-Type": "application/json"},
    stream=True,
)
for line in response.iter_lines(decode_unicode=True):
    if line:
        print(line, flush=True)
