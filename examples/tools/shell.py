"""End-to-end Agentor example: ShellTool.

Environment:
    export OPENAI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.tools import ShellTool


def main() -> None:
    agent = Agentor(
        name="Shell Agent",
        model="gpt-5-mini",
        tools=[ShellTool()],
        instructions="Use shell commands to inspect the local project safely.",
    )

    result = agent.run(
        "Use the shell tool to run `pwd` and then `ls` in the current directory. Return both outputs."
    )
    print(result.final_output)


if __name__ == "__main__":
    main()
