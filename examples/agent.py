import dotenv


from agentor.agents import Agentor, get_dummy_weather

dotenv.load_dotenv()

agent = Agentor(
    name="Agentor",
    instructions="Give output like in Haiku format.",
    model="gpt-5-mini",
    tools=[get_dummy_weather],
)

result = agent.think("What is the weather in Tokyo?")
print(result)
