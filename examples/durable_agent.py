"""Durable runs: every event is persisted, so a run can be resumed.

Durability is a property of the native engine rather than a separate agent
class - pass a store and the run becomes recoverable.
"""

from agentor import Agentor
from agentor.engine.store import FileStore
from agentor.tools import GetWeatherTool


def main():
    agent = Agentor(
        name="Weather Agent",
        model="gpt-5-mini",
        tools=[GetWeatherTool()],
        store=FileStore("runs"),
    )

    print("\n--- Starting New Run ---")
    result = agent.run("What is the weather in San Francisco?")

    print(f"Run ID: {result.run_id}")
    print(f"Status: {result.status}")
    print(f"Final Answer: {result.final_output}")

    # Resuming a finished run returns the stored result instead of re-running
    # it, so this is safe to call whether or not the process crashed.
    print("\n--- Resuming ---")
    resumed = agent.resume(result.run_id)
    print(f"Status: {resumed.status}")
    print(f"Final Answer: {resumed.final_output}")


if __name__ == "__main__":
    main()
