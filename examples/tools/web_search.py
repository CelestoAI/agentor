"""End-to-end Agentor example: WebSearchTool.

Environment:
    export OPENAI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.tools import WebSearchTool


def main() -> None:
    agent = Agentor(
        name="Web Search Agent",
        model="gpt-5-mini",
        tools=[WebSearchTool()],
        instructions="Use web search when up-to-date information is requested.",
    )

    result = agent.run("Find 3 recent updates about Model Context Protocol.")
    print(result.final_output)


if __name__ == "__main__":
    main()
