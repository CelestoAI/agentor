"""End-to-end Agentor example: GitTool.

Requirements:
    pip install "agentor[git]"

Environment:
    export GIT_REPO_PATH=/absolute/path/to/your/repo
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import GitTool


def main() -> None:
    repo_path = os.environ.get("GIT_REPO_PATH", ".")

    agent = Agentor(
        name="Git Assistant",
        model="gpt-5-mini",
        tools=[GitTool()],
        instructions="Use git tool operations for repository actions.",
    )

    result = agent.run(
        f"Use the git tool to run status on repo_path='{repo_path}' and summarize what is changed."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
