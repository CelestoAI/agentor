"""End-to-end Agentor example: GmailTool.

Requirements:
    pip install "agentor[google]"

Environment:
    export GOOGLE_USER_CREDENTIALS=/path/to/credentials.json
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import GmailTool


def main() -> None:
    credentials_path = os.environ.get("GOOGLE_USER_CREDENTIALS", "credentials.json")

    agent = Agentor(
        name="Gmail Assistant",
        model="gpt-5-mini",
        tools=[GmailTool(credentials_path=credentials_path)],
        instructions="Use Gmail tool capabilities to search and inspect messages.",
    )

    result = agent.run(
        "Use Gmail search_messages with query 'newer_than:7d' and return the top 5 recent messages with sender and subject."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
