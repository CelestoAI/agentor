"""End-to-end Agentor example: FetchTool.

Environment:
    export OPENAI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.tools import FetchTool


def main() -> None:
    agent = Agentor(
        name="Fetch Agent",
        model="gpt-5-mini",
        tools=[FetchTool()],
        instructions="Use the fetch tool when you need to retrieve webpage content.",
    )

    result = agent.run(
        "Use fetch_url on https://celesto.ai/blog and summarize the page in 3 concise bullet points."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
