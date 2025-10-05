import asyncio
import os
from dataclasses import dataclass
from typing import Optional

import typer
from agents import Agent, Runner, SQLiteSession
from dotenv import load_dotenv
from openai.types.responses import ResponseOutputItemAddedEvent, ResponseTextDeltaEvent
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.text import Text

from agentor.agenthub import main_agent
from agentor.integrations.google.google_agent import create_google_context

load_dotenv()

app = typer.Typer()
console = Console()

# Use your main agent and add session memory
agent: Agent = main_agent
session = SQLiteSession("chat_session")  # persistent memory via SQLite


@dataclass
class ChatConfig:
    show_tool_output: bool = False
    tool_output_max_chars: int = 500
    gmail_user_id: Optional[str] = None
    model_override: Optional[str] = None


async def run_agent_stream(input_text: str, config: ChatConfig, context):
    console.print("[bold green]AI:[/bold green] ", end="")

    result_stream = Runner.run_streamed(
        agent,
        input=input_text,
        session=session,
        context=context,
    )

    try:
        async for event in result_stream.stream_events():
            if event.type == "agent_updated_stream_event":
                console.print(f"\n[dim]Agent updated: {event.new_agent.name}[/dim]")

            elif event.type == "raw_response_event":
                if isinstance(event.data, ResponseTextDeltaEvent):
                    console.print(event.data.delta, end="", soft_wrap=True)
                elif (
                    isinstance(event.data, ResponseOutputItemAddedEvent)
                    and event.data.item.type == "reasoning"
                ):
                    console.print("\n[dim](reasoning...)[/dim]")
                else:
                    continue

            elif event.type == "run_item_stream_event":
                if event.item.type == "tool_call_item":
                    tool_name = getattr(event.item, "tool_name", None)
                    if tool_name:
                        console.print(
                            f"\n[bold yellow]🔧 Running tool:[/bold yellow] {tool_name}"
                        )
                    else:
                        console.print(
                            f"\n[bold yellow]🔧 Running tool...[/bold yellow] {event.item.raw_item.name}"
                        )
                elif event.item.type == "tool_call_output_item":
                    if config.show_tool_output:
                        raw_output = str(getattr(event.item, "output", ""))
                        truncated = (
                            raw_output
                            if len(raw_output) <= config.tool_output_max_chars
                            else raw_output[: config.tool_output_max_chars]
                            + " … [dim](truncated)[/dim]"
                        )
                        console.print(
                            Panel(
                                truncated,
                                title="Tool output",
                                title_align="left",
                                expand=False,
                                border_style="cyan",
                            )
                        )

            elif event.type == "error":
                console.print(f"\n[red]Error:[/red] {event}")
                return

            else:
                console.print(f"\n[dim]Unhandled event type: {event}[/dim]")

        console.print()  # newline when done

        # Optionally display final_output summary
        # console.print(f"[bold green]AI ended with:[/bold green] {result_stream.final_output}")

    except Exception as e:
        console.print(f"\n[red]An error occurred:[/red] {e}")


def _print_help():
    help_text = Text()
    help_text.append("Commands:\n", style="bold")
    help_text.append("  /help                Show this help\n")
    help_text.append("  /exit or /quit       Exit chat\n")
    help_text.append("  /set user <id>       Set Gmail user id for this session\n")
    help_text.append("  /tools on|off        Toggle printing tool outputs\n")
    help_text.append("  /model <name>        Override model for this session\n")
    help_text.append('\nMultiline: enter triple quotes (""") on a line to start/end.')
    console.print(Panel(help_text, title="Chat help", expand=False))


def _read_input() -> str:
    first = Prompt.ask("\n[bold blue]You[/bold blue]")
    if first.strip() == '"""':
        console.print('[dim]Enter text, end with """ on its own line[/dim]')
        lines: list[str] = []
        while True:
            line = Prompt.ask("")
            if line.strip() == '"""':
                break
            lines.append(line)
        return "\n".join(lines)
    return first


@app.command()
def chat(
    gmail_user_id: Optional[str] = typer.Option(
        None, "--gmail-user-id", "-u", help="Gmail user id for the Gmail tools context"
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m", help="Override base model for the main agent"
    ),
    show_tools: bool = typer.Option(
        False,
        "--show-tools/--hide-tools",
        help="Print tool outputs while streaming",
    ),
):
    # Configure from CLI or env
    cfg = ChatConfig(
        show_tool_output=show_tools,
        gmail_user_id=gmail_user_id or os.getenv("AGENTOR_GMAIL_USER_ID"),
        model_override=model or os.getenv("AGENTOR_MODEL_OVERRIDE"),
    )

    # Create context with optional user_id override
    google_context = create_google_context(user_id=cfg.gmail_user_id)

    if cfg.model_override:
        agent.model = cfg.model_override

    console.print(
        Panel(
            Text.from_markup(
                "Chat ready. Type something (or '/exit').\n"
                "[dim]Hint: /help for commands. Gmail user: "
                + (cfg.gmail_user_id or "(default)")
                + ", model: "
                + (agent.model or "(default)")
            ),
            expand=False,
        )
    )

    while True:
        try:
            user_input = _read_input()
        except (KeyboardInterrupt, EOFError):
            console.print("\nGoodbye.")
            break

        cmd = user_input.strip()
        if cmd in {"/exit", "/quit", "exit", "quit"}:
            console.print("Goodbye.")
            break
        if cmd == "/help":
            _print_help()
            continue
        if cmd.startswith("/set user "):
            new_id = cmd[len("/set user ") :].strip()
            if new_id:
                google_context = create_google_context(user_id=new_id)
                cfg.gmail_user_id = new_id
                console.print(f"[dim]Gmail user set to[/dim] [bold]{new_id}[/bold]")
            else:
                console.print("[red]Usage:[/red] /set user <id>")
            continue
        if cmd.startswith("/tools "):
            arg = cmd[len("/tools ") :].strip().lower()
            if arg in {"on", "off"}:
                cfg.show_tool_output = arg == "on"
                console.print(
                    f"[dim]Tool outputs[/dim] {'[bold]ON[/bold]' if cfg.show_tool_output else '[bold]OFF[/bold]'}"
                )
            else:
                console.print("[red]Usage:[/red] /tools on|off")
            continue
        if cmd.startswith("/model "):
            new_model = cmd[len("/model ") :].strip()
            if new_model:
                agent.model = new_model
                cfg.model_override = new_model
                console.print(f"[dim]Model set to[/dim] [bold]{new_model}[/bold]")
            else:
                console.print("[red]Usage:[/red] /model <name>")
            continue

        asyncio.run(run_agent_stream(user_input, cfg, google_context))


if __name__ == "__main__":
    app()
