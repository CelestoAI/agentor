# 🚀 Serving an Agent with Agentor

This example shows how to run a **scalable, production-ready Agent server** using `Agentor` ✴️.

We’ll integrate Agentor with the built-in weather tool (set `WEATHER_API_KEY` for live data) to create a weather-aware conversational agent.

## 🔧 Key Features

- ⚡️ Scalable inference powered by `Agentor`
- 🔄 Async streaming for real-time interaction
- 🧩 Custom tools via the `@function_tool` decorator (e.g., get_weather, search_docs, or your own functions)

## Example

Here’s an example of serving an Agentor instance with a simple weather tool in just a few lines of code.

```python
from agentor import Agentor

agent = Agentor(
    name="Agentor",
    model="gpt-5-mini",
    tools=["get_weather"],
)

agent.serve(port=8000)
```

## Query the Agent server

Once the server is running, you can send chat requests using curl or any HTTP client:

```bash
curl -X 'POST' \
  'http://localhost:8000/chat' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "input": "What is the weather in London?"
}'
```

The Agent server will respond asynchronously — ideal for streaming, scalable, and multi-agent applications.

## Hosting

`agent.serve()` runs an ordinary ASGI app under uvicorn, so deploy it the way you
deploy any other Python service — a container, a process manager, or whatever
your platform expects.
