import asyncio

import dotenv

from agentor.core import Agentor, get_dummy_weather

dotenv.load_dotenv()

agent = Agentor(
    name="Agentor",
    model="gpt-5-mini",
    tools=[get_dummy_weather],
)


async def main():
    async for event in agent.stream_chat(
        "How is the weather in Tokyo?",
    ):
        print(event, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
