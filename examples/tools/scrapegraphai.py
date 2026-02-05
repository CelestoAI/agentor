"""End-to-end Agentor example: ScrapeGraphAI.

Requirements:
    pip install "agentor[scrape_graph_ai]"

Environment:
    export SCRAPEGRAPH_API_KEY=your_scrapegraph_key
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import ScrapeGraphAI


def main() -> None:
    api_key = os.environ.get("SCRAPEGRAPH_API_KEY")
    if not api_key:
        raise ValueError("SCRAPEGRAPH_API_KEY is required")

    agent = Agentor(
        name="ScrapeGraph Agent",
        model="gpt-5-mini",
        tools=[ScrapeGraphAI(api_key=api_key)],
        instructions="Use ScrapeGraphAI tools for extraction from websites.",
    )

    result = agent.run(
        "Use smartscraper on https://example.com and extract the page title and a short summary."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
