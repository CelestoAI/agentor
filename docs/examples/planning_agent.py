import dotenv


from agentor.agents import Agentor, get_dummy_weather

dotenv.load_dotenv()

agent = Agentor(
    name="Agentor",
    model="gpt-5-mini",
    tools=[get_dummy_weather],
)

result = agent.think("How do I measure the angle between the sun and the earth?")
print(result)
