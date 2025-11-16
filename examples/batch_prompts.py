import asyncio
from agentor import Agentor


async def main():
    agent = Agentor(name="Assistant", model="gpt-5-mini")
    results = await agent.arun(
        ["What is the weather in London?", "What is the weather in Paris?"]
    )
    for result in results:
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
