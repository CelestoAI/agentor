import asyncio
import random
import logging
import typer
from rich.console import Console
from rich.theme import Theme
from rich.prompt import Prompt
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner
from zerozen.agenthub import main_agent

logger = logging.getLogger(__name__)

app = typer.Typer()

# Rich theme for sass
custom_theme = Theme(
    {
        "sassy": "bold magenta",
        "shade": "italic white on black",
        "wink": "underline yellow",
    }
)
console = Console(theme=custom_theme)

# Use your configured agent
agent: Agent = main_agent


def get_shade_prefix() -> str:
    return random.choice(
        [
            "[shade]Really?[/shade] ",
            "[sassy]Oh please…[/sassy] ",
            "[wink]*side‑eye*[/wink] ",
        ]
    )


async def run_agent_stream(input_text: str):
    shade = get_shade_prefix()
    console.print(f"[bold green]AI:[/bold green] {shade}", end="")

    result_stream = Runner.run_streamed(agent, input=input_text)

    try:
        async for event in result_stream.stream_events():
            match event.type:
                case "agent_updated_stream_event":
                    console.print(
                        f"\n[shade](psst... new agent in charge: {event.new_agent.name})[/shade]"
                    )
                    continue

                case "raw_response_event":
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        console.print(event.data.delta, end="", soft_wrap=True)
                    else:
                        logger.debug(f"Unknown raw response content: {event.data}")

                case "run_item_stream_event":
                    match event.item.type:
                        case "tool_call_item":
                            console.print(
                                "\n[bold yellow]🔎 Researching...[/bold yellow]"
                            )
                        case "tool_call_output_item":
                            # You can print output if needed
                            pass

                case "error":
                    logger.error(f"Error: {event.error}")
                    return

                case _:
                    logger.debug(f"Unhandled event type: {event.type}")

        console.print()  # newline at the end

    except Exception as e:
        console.print(f"\n[sassy]Drama alert:[/sassy] {e}")


@app.command()
def chat():
    console.print(
        "[sassy]Hola, darling! I’m your sass‑charged AI agent. Type something (or 'exit').[/sassy]"
    )
    while True:
        user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
        if user_input.strip().lower() in {"exit", "quit"}:
            console.print("[sassy]Later, alligator 🙄[/sassy]")
            break
        asyncio.run(run_agent_stream(user_input))


if __name__ == "__main__":
    app()
