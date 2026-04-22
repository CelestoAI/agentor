"""
Example: Using ScrapeGraphAI tool with Agentor/Celesto

This example demonstrates how to use the ScrapeGraphAI tool (scrapegraph-py
SDK v2) to scrape, extract, search, crawl and monitor the web.

Install the required dependency:
    pip install agentor[scrapegraph]

Set your ScrapeGraphAI API key as an environment variable:
    export SGAI_API_KEY=your_api_key_here
"""

import asyncio
import os

import dotenv

from agentor import Agentor
from agentor.tools import ScrapeGraphAI

dotenv.load_dotenv()

scrapegraph_tool = ScrapeGraphAI(api_key=os.environ.get("SGAI_API_KEY"))

agent = Agentor(
    name="Web Scraping Agent",
    model="gpt-5-mini",
    tools=[scrapegraph_tool],
)


async def main():
    """Example usage of ScrapeGraphAI with Agentor."""

    print("=== Example 1: Scrape (markdown) ===")
    result = await agent.arun(
        "Use scrape to fetch https://www.example.com as markdown and show the first lines."
    )
    print(result.final_output)
    print("\n")

    print("=== Example 2: Extract ===")
    result = await agent.arun(
        "Use extract to pull the page title and description from https://www.example.com."
    )
    print(result.final_output)
    print("\n")

    print("=== Example 3: Search ===")
    result = await agent.arun(
        "Use search to find 3 results about Python web scraping libraries."
    )
    print(result.final_output)
    print("\n")

    print("=== Example 4: Crawl ===")
    result = await agent.arun(
        "Use crawl to start a crawl of https://www.example.com with max_pages=3 and max_depth=1, "
        "then use get_crawl_result with the returned id to show its status."
    )
    print(result.final_output)
    print("\n")

    print("=== Example 5: Credits ===")
    result = await agent.arun("Use credits to show my remaining API credits.")
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
