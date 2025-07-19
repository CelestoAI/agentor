from agents import Agent
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from .web_search import web_search_agent


coder_agent = Agent(
    name="coder_agent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are an expert coder.""",
    model="gpt-4o",
    tools=[
        web_search_agent.as_tool(
            tool_name="web_search",
            tool_description="Search the web for information on coding related topics",
        )
    ],
)

main_agent = Agent(
    name="main_agent",
    instructions="You are a helpful assistant.",
    handoffs=[coder_agent],
    model="gpt-4o-mini",
)
