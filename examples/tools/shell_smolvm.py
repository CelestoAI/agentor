"""End-to-end Agentor example: ShellTool + SmolVMRuntime.

Requirements:
    pip install smolvm
    # Follow host setup docs: https://docs.celesto.ai/smolvm/getting-started

Environment:
    export OPENAI_API_KEY=your_llm_key
"""

from agentor import Agentor
from agentor.runtime import SmolVMRuntime
from agentor.tools import ShellTool


def main() -> None:
    runtime = SmolVMRuntime(mem_size_mib=1024, disk_size_mib=2048)

    try:
        agent = Agentor(
            name="SmolVM Shell Agent",
            model="gpt-5-mini",
            tools=[ShellTool(executor=runtime)],
            instructions="Use shell commands to inspect files inside the SmolVM sandbox.",
        )

        result = agent.run(
            "Use the shell tool to run `pwd` and then `ls` in the sandbox. Return both outputs."
        )
        print(result)
    finally:
        runtime.close()


if __name__ == "__main__":
    main()
