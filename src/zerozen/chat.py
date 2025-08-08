import asyncio
import random
import typer
from rich.console import Console
from rich.theme import Theme
from rich.prompt import Prompt
from openai.types.responses import ResponseTextDeltaEvent
from agents import Agent, Runner, SQLiteSession
from zerozen.agenthub import main_agent, gmail_context

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

# Use your main agent and add session memory
agent: Agent = main_agent
session = SQLiteSession("chat_session")  # persistent memory via SQLite


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

    result_stream = Runner.run_streamed(
        agent, input=input_text, session=session, context=gmail_context
    )

    try:
        async for event in result_stream.stream_events():
            match event.type:
                case "agent_updated_stream_event":
                    console.print(
                        f"\n[shade](psst... new agent in charge: {event.new_agent.name})[/shade]"
                    )

                case "raw_response_event":
                    if isinstance(event.data, ResponseTextDeltaEvent):
                        console.print(event.data.delta, end="", soft_wrap=True)
                    else:
                        console.print("[dim](unexpected raw response)[/dim]", end="")

                case "run_item_stream_event":
                    match event.item.type:
                        case "tool_call_item":
                            console.print(
                                "\n[bold yellow]🔧 Running tool...[/bold yellow]"
                            )
                        case "tool_call_output_item":
                            # Optionally print tool output
                            console.print(
                                f"\n[bold cyan]Tool returned:[/bold cyan] {event.item.output}"
                            )

                case "error":
                    console.print(f"\n[sassy]Drama alert:[/sassy] {event.error}")
                    return

                case _:
                    console.print(f"\n[dim]Unhandled event type: {event.type}[/dim]")

        console.print()  # newline when done

        # Optionally display final_output summary
        # console.print(f"[bold green]AI ended with:[/bold green] {result_stream.final_output}")

    except Exception as e:
        console.print(f"\n[sassy]Oh no babe, something broke:[/sassy] {e}")


@app.command()
def chat():
    console.print(
        "[sassy]Hola, darling! I’ll remember everything now. Type something (or 'exit').[/sassy]"
    )
    while True:
        user_input = Prompt.ask("\n[bold blue]You[/bold blue]")
        if user_input.strip().lower() in {"exit", "quit"}:
            console.print("[sassy]Ciao! I’ll remember you (until next time) 🙄[/sassy]")
            break
        asyncio.run(run_agent_stream(user_input))


if __name__ == "__main__":
    app()
