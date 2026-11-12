"""End-to-end Agentor example: ShellTool + BoxdRuntime.

Requirements:
    pip install boxd
    # Create an API key: https://docs.boxd.sh/cli/authentication?ref=agentor#api-keys

Environment:
    export BOXD_API_KEY=your_boxd_key
    export GEMINI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.runtime import BoxdRuntime
from agentor.tools import ShellTool


def main() -> None:
    runtime = BoxdRuntime()

    try:
        agent = Agentor(
            name="boxd Shell Agent",
            model="gemini/gemini-flash-latest",
            tools=[ShellTool(executor=runtime)],
            instructions="Use shell commands to inspect files inside the boxd machine.",
        )

        result = agent.run(
            "Use the shell tool to run `pwd` and then `uname -a` in the machine. Return both outputs."
        )
        print(result.final_output)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
