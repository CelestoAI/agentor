from agents import Agent
from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from .web_search import web_search_agent
from zerozen.integrations.gmail.agent import build_gmail_agent_and_context


concept_research_agent = Agent(
    name="Concept research agent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are an expert concept researcher. For every request, think about the topic, language, and complexity of the request.
You must use the web_search tool to get latest information about the topic. Replan the implementation and write the code.
""",
    model="gpt-4o",
    tools=[
        web_search_agent.as_tool(
            tool_name="web_search",
            tool_description="Search the web for information on coding related topics",
        )
    ],
)


coder_agent = Agent(
    name="Coder agent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are an expert coder. For every request, think about the topic, language, and complexity of the request.
You must use the web_search tool to get latest information about the topic. Replan the implementation and write the code.
""",
    model="gpt-4o",
    handoffs=[concept_research_agent],
)

gmail_agent, gmail_context = build_gmail_agent_and_context()

main_agent = Agent(
    name="Triage agent",
    instructions="Handoff to the appropriate agent based on the language of the request.",
    handoffs=[coder_agent, gmail_agent],
)
