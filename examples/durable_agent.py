from agentor.durable import DurableAgent
from agentor.tools import GetWeatherTool


def main():
    # Initialize the tool
    weather_tool = GetWeatherTool()

    # Initialize the agent
    agent = DurableAgent(
        model="openai/gpt-5-mini",
        tools=[weather_tool],
    )

    print("\n--- Starting New Run ---")
    input_text = "What is the weather in San Francisco?"
    result = agent.run(input_text=input_text)

    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Final Answer: {result.final_answer}")


if __name__ == "__main__":
    main()
