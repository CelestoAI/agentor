import litserve as ls
from agentor import Agentor

# CELESTO_API_TOKEN = os.environ.get("CELESTO_API_TOKEN")


# @function_tool
# def get_weather(city: str) -> str:
#     """Returns the weather in the given city."""
#     try:
#         client = CelestoSDK(CELESTO_API_TOKEN)
#         return client.toolhub.run_weather_tool(city)
#     except Exception as e:
#         print(f"Error: {e}")
#         return "Failed to get weather data."


class AgentorServer(ls.LitAPI):
    def setup(self, device):
        self.agentor = Agentor(
            name="Agentor", model="gpt-5-mini", tools=["get_weather"]
        )

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
