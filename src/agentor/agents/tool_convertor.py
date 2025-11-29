"""
from agentor import tool, Agentor, LLM

@tool
def get_weather(city: str):
    return "The weather in London is sunny"

# using Agent
agent = Agentor(tools=[get_weather])
agent.run("What is the weather in London?")

# using LLM
llm = LLM(tools=[get_weather])
llm.chat("What is the weather in London?")
"""
