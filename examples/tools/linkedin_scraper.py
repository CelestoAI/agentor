"""End-to-end Agentor example: LinkedInScraperTool.

Environment:
    export BRIGHT_DATA_API_KEY=your_bright_data_key
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import LinkedInScraperTool


def main() -> None:
    if not os.environ.get("BRIGHT_DATA_API_KEY"):
        raise ValueError("BRIGHT_DATA_API_KEY is required")

    profile_url = os.environ.get(
        "LINKEDIN_PROFILE_URL", "https://www.linkedin.com/in/satyanadella/"
    )

    agent = Agentor(
        name="LinkedIn Scraper Agent",
        model="gpt-5-mini",
        tools=[LinkedInScraperTool()],
        instructions="Use the LinkedIn scraper tool for profile extraction.",
    )

    result = agent.run(
        f"Use scrape_profile on '{profile_url}' and summarize key profile details in bullets."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
