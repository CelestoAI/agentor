"""
Example: Using ScrapeGraphAI tool with Agentor/Celesto

This example demonstrates how to use the ScrapeGraphAI tool to scrape websites
and extract information using AI-powered scraping capabilities.

Make sure to install the required dependency:
    pip install agentor[scrape_graph_ai]

Set your ScrapeGraphAI API key as an environment variable:
    export SCRAPEGRAPH_API_KEY=your_api_key_here
"""

import asyncio
import os

import dotenv
from agentor import Agentor
from agentor.tools import ScrapeGraphAI

dotenv.load_dotenv()

# Initialize ScrapeGraphAI tool with API key from environment
scrapegraph_tool = ScrapeGraphAI(api_key=os.environ.get("SCRAPEGRAPH_API_KEY"))

# Create an agent with ScrapeGraphAI tool
agent = Agentor(
    name="Web Scraping Agent",
    model="gpt-5-mini",
    tools=[scrapegraph_tool],
)


async def main():
    """Example usage of ScrapeGraphAI with Agentor."""
    
    # Example 1: Smart scraper - extract specific information from a website
    print("=== Example 1: Smart Scraper ===")
    result = await agent.arun(
        "Use smartscraper to extract the main title and description from https://www.example.com"
    )
    print(result.final_output)
    print("\n")
    
    # Example 2: Search scraper - search and extract information
    print("=== Example 2: Search Scraper ===")
    result = await agent.arun(
        "Use searchscraper to find information about Python programming tutorials"
    )
    print(result.final_output)
    print("\n")
    
    # Example 3: Markdownify - convert website to markdown
    print("=== Example 3: Markdownify ===")
    result = await agent.arun(
        "Use markdownify to convert https://www.example.com to markdown format"
    )
    print(result.final_output)
    print("\n")
    
    # Example 4: Smart Crawler - crawl multiple pages
    print("=== Example 4: Smart Crawler ===")
    result = await agent.arun(
        "Use smartcrawler to extract all product information from https://www.example.com with max_depth=2 and max_pages=5"
    )
    print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())
