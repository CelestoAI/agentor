import asyncio

from agentor.mcp import MCPServerStreamableHttp
from agentor import Agentor


async def main() -> None:
    async with MCPServerStreamableHttp(
        name="Streamable HTTP Python Server",
        params={
            "url": "http://localhost:8000/mcp",
            "timeout": 10,
        },
        cache_tools_list=True,
        max_retry_attempts=3,
    ) as server:
        agent = Agentor(
            name="Assistant",
            instructions="Use the MCP tools to answer the questions.",
            tools=[server],
        )
        result = await agent.arun("Add 7 and 22.")
        print(result.final_output)


asyncio.run(main())
