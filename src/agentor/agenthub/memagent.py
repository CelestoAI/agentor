from agents import Agent

from agentor.memory.tools import memory_add, memory_get_full_conversation, memory_search

_instructions = """
You are a memory agent. You are responsible for finding relevent information from the memory for the user's request and updating the memory with the new information.

You have the following tools:
- memory_search tool to search the memory for the most relevant conversations.
- memory_get_full_conversation tool to get the full conversation from the memory.
- memory_add tool to add a conversation to the memory.
"""


def build_memory_agent(model: str = "gpt-5-mini") -> Agent:
    return Agent(
        name="Memory agent",
        instructions=_instructions,
        tools=[memory_search, memory_get_full_conversation, memory_add],
        model=model,
    )
