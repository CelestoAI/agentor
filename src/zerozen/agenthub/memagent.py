from agents import Agent
from zerozen.memory.tools import memory_search, memory_get_full_conversation, memory_add

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


if __name__ == "__main__":
    from agents import Runner, RunContextWrapper
    from zerozen.utils import AppContext
    from zerozen.memory.api import Memory

    agent = build_memory_agent()
    runner = Runner()
    output = runner.run_sync(
        agent,
        "What is the capital of France?",
        context=RunContextWrapper(AppContext(None, None, None, Memory())),
    )
    print(output)
