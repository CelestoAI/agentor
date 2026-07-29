from agentor import Agentor

agent = Agentor.from_md("AGENTS.md")
result = agent.run("Weather in Paris?")
print(result)
