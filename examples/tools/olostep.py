"""End-to-end Agentor example: OlostepTool.

Environment:
    export OPENAI_API_KEY=your_llm_key
    export OLOSTEP_API_KEY=your_olostep_key

Install olostep extra:
    pip install "agentor[olostep]"
"""

import asyncio
import os

import dotenv

from agentor import Agentor
from agentor.tools import OlostepTool

dotenv.load_dotenv()

olostep = OlostepTool(api_key=os.environ.get("OLOSTEP_API_KEY"))

agent = Agentor(
    name="Web Research Agent",
    model="gpt-5-mini",
    tools=[olostep],
    instructions=(
        "You are a helpful research assistant. "
        "Use Olostep tools to scrape websites, search the web, "
        "and get AI-powered answers when needed."
    ),
)


async def main():
    """Showcase core OlostepTool capabilities."""

    # 1. Scrape a webpage
    print("=== Scrape ===")
    result = await agent.arun("Scrape https://example.com and summarize the page.")
    print(result.final_output)
    print()

    # 2. Web search
    print("=== Web Search ===")
    result = await agent.arun("Search the web for 'Model Context Protocol' and summarize the top results.")
    print(result.final_output)
    print()

    # 3. AI answers
    print("=== AI Answers ===")
    result = await agent.arun(
        "Use the answers tool to find out: Who are the top 3 competitors to Vercel?"
    )
    print(result.final_output)
    print()

    # 4. Map a website
    print("=== Map Website ===")
    result = await agent.arun(
        "Discover all URLs on https://docs.celesto.ai related to 'tools' and list them."
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
