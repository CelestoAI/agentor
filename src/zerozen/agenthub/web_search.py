import asyncio

from agents import Agent, Runner, WebSearchTool, trace

web_search_tool = WebSearchTool(user_location={"type": "approximate"})

web_search_agent = Agent(
    name="Web searcher",
    instructions="You are a helpful agent.",
    model="gpt-4o",
    tools=[web_search_tool],
)


async def main():
    agent = Agent(
        name="Web searcher",
        instructions="You are a helpful agent.",
        tools=[web_search_tool],
    )

    with trace("Web search example"):
        result = await Runner.run(
            agent,
            "search the web for 'local sports news' and give me 1 interesting update in a sentence.",
        )
        print(result.final_output)
        # The New York Giants are reportedly pursuing quarterback Aaron Rodgers after his ...


if __name__ == "__main__":
    asyncio.run(main())
