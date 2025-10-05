from agents import Agent, WebSearchTool

web_search_tool = WebSearchTool(user_location={"type": "approximate"})

web_search_agent = Agent(
    name="Web searcher",
    instructions="Rephrase the user's request into a search query and use the web_search tool to get the information.",
    model="gpt-4o-mini",
    tools=[web_search_tool],
)
