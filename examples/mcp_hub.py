from agentor import Agentor, CelestoMCPHub
import asyncio


async def main():
    async with CelestoMCPHub() as mcp_hub:
        agent = Agentor(name="Weather Agent", model="gpt-5-mini", tools=[mcp_hub])
        result = await agent.arun("What is the weather in London?")
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
