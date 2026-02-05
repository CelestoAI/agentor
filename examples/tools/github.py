"""End-to-end Agentor example: GitHubTool.

Requirements:
    pip install "agentor[github]"

Environment:
    export GITHUB_TOKEN=your_github_token
    export GITHUB_REPO=owner/repo  # optional, defaults to octocat/Hello-World
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import GitHubTool


def main() -> None:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN is required")

    repo = os.environ.get("GITHUB_REPO", "octocat/Hello-World")

    agent = Agentor(
        name="GitHub Agent",
        model="gpt-5-mini",
        tools=[GitHubTool(access_token=token)],
        instructions="Use the GitHub tool for repository issue operations.",
    )

    result = agent.run(
        f"Use the GitHub tool to fetch issue #1 from '{repo}' and summarize the title, state, and body."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
