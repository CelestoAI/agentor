"""
CLI commands for ZeroZen chat interface.
"""

import typer
from rich import print
from .app import run_chat

app = typer.Typer(name="chat", help="Chat interface commands")


@app.command()
def start():
    """Launch the interactive chat interface."""
    print("[bold green]🧘‍♂️ Launching ZeroZen Chat Interface...[/bold green]")
    run_chat()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    """Default chat command - launches the interface."""
    if ctx.invoked_subcommand is None:
        start()
