"""End-to-end Agentor example: SlackTool.

Requirements:
    pip install "agentor[slack]"

Environment:
    export SLACK_BOT_TOKEN=xoxb-...
    export OPENAI_API_KEY=your_llm_key
"""

import os

from agentor import Agentor
from agentor.tools import SlackTool


def main() -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        raise ValueError("SLACK_BOT_TOKEN is required")

    agent = Agentor(
        name="Slack Agent",
        model="gpt-5-mini",
        tools=[SlackTool(token=token)],
        instructions="Use Slack tool capabilities to inspect and communicate in workspace channels.",
    )

    result = agent.run("Use list_channels and return the first 10 channels.")
    print(result.final_output)


if __name__ == "__main__":
    main()
