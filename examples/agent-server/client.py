import requests

response = requests.post(
    "http://127.0.0.1:8000/chat",
    json={"input": "What is the weather in London?"},
    stream=True,
)
for line in response.iter_lines():
    if line:
        print(line, flush=True)
