"""End-to-end Agentor example: ExaSearchTool.

Requirements:
    pip install "agentor[exa]"

Environment:
    export EXA_API_KEY=your_exa_key
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import ExaSearchTool


def main() -> None:
    exa_api_key = os.environ.get("EXA_API_KEY")
    if not exa_api_key:
        raise ValueError("EXA_API_KEY is required")

    agent = Agentor(
        name="Exa Search Agent",
        model="gpt-5-mini",
        tools=[ExaSearchTool(api_key=exa_api_key)],
        instructions="Always use the Exa search tool for web lookups.",
    )

    result = agent.run(
        "Use the Exa tool to find 3 recent updates about Model Context Protocol and summarize them in bullets."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
