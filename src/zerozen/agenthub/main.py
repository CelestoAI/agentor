from agents import Agent, ModelSettings
from openai.types.shared import Reasoning

from agents.extensions.handoff_prompt import RECOMMENDED_PROMPT_PREFIX

from .web_search import web_search_agent
from zerozen.integrations.google.google_agent import build_google_agent_and_context


concept_research_agent = Agent(
    name="Concept research agent",
    instructions=f"""{RECOMMENDED_PROMPT_PREFIX}
You are an expert concept researcher. For every request, think about the topic, language, and complexity of the request.
You must use the web_search tool to get latest information about the topic. Replan the implementation and write the code.
""",
    model="gpt-5",
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
    model="gpt-5",
    handoffs=[concept_research_agent],
)

google_agent, google_context = build_google_agent_and_context()

main_agent = Agent(
    name="Triage agent",
    instructions="Handoff to the appropriate agent whenever required. E.g. when the user asks for a code, handoff to the coder agent.",
    handoffs=[coder_agent, google_agent],
    model="gpt-5",
    model_settings=ModelSettings(
        reasoning=Reasoning(
            effort="minimal",
        )
    ),
)
