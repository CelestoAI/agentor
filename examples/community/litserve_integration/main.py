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
