# 🚀 Agent Deployment

This example demonstrates how to deploy a scalable Agent server using [LitServe](https://github.com/Lightning-AI/LitServe) ⚡️ — an open-source Python library optimized for production-scale inference and async streaming.

We’ll integrate Agentor with the built-in weather tool (set `WEATHER_API_KEY` for live data) to create a weather-aware conversational agent.

Below is an example of deploying an Agentor instance with a simple weather tool using LitServe.

```python
import os
import litserve as ls
from agentor import Agentor
from agentor.tools import GetWeatherTool


class AgentorServer(ls.LitAPI):
    def setup(self, device):
        weather_tool = GetWeatherTool(api_key=os.environ.get("WEATHER_API_KEY"))
        self.agentor = Agentor(name="Agentor", model="gpt-5-mini", tools=[weather_tool])

    async def predict(self, request: dict):
        async for event in self.agentor.stream_chat(
            request["query"], output_format="json"
        ):
            yield event

    async def encode_response(self, output, **kwargs):
        async for item in output:
            yield item


if __name__ == "__main__":
    api = AgentorServer(stream=True, enable_async=True, api_path="/chat")
    server = ls.LitServer(api)
    server.run(port=8000)
```

## ☁️ Deploying to the Cloud

To deploy this server, run the following:

```
lightning deploy main.py --cloud
```

Once deployed, your Agent server will be available as a scalable, async-ready API endpoint.

## 🔧 Key Features

- Scalable inference powered by LitServe
- Async streaming responses for real-time interaction
- Custom tools (like get_weather) via `@function_tool`
- Simple cloud deployment using lightning deploy
