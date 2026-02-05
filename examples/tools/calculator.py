"""End-to-end Agentor example: CalculatorTool.

Environment:
    export OPENAI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.tools import CalculatorTool


def main() -> None:
    agent = Agentor(
        name="Calculator Agent",
        model="gpt-5-mini",
        tools=[CalculatorTool()],
        instructions="You are a precise math assistant. Always use the calculator tool for arithmetic.",
    )

    result = agent.run(
        "Use the calculator tool to compute (37 * 12) - (144 / 3). Return only the final number."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
