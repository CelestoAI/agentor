from agentor import Agentor

# This example uses the get_weather tool from the Celesto AI Tool Hub registry
agent = Agentor(
    name="Weather Agent",
    model="gpt-5-mini",
    tools=["get_weather"],
)

result = agent.run("What is the weather in London?")
print(result)
