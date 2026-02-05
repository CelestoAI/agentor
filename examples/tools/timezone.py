"""End-to-end Agentor example: TimezoneTool.

Environment:
    export OPENAI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.tools import TimezoneTool


def main() -> None:
    agent = Agentor(
        name="Timezone Agent",
        model="gpt-5-mini",
        tools=[TimezoneTool()],
        instructions="Use the timezone tool for current-time requests.",
    )

    result = agent.run(
        "Use the timezone tool to get current time in UTC, America/New_York, and Asia/Kolkata."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
