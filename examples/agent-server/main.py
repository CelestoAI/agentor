from agentor import Agentor

agent = Agentor(
    name="Agentor",
    model="gpt-5-mini",
    tools=["get_weather"],
)

agent.serve(port=8000)
