from __future__ import annotations

import typer
from rich import print

from . import a2a, deployment, proxy

app = typer.Typer()
app.add_typer(proxy.app)
app.add_typer(a2a.app, name="a2a")

# Add deployment commands at top level
app.command("deploy")(deployment.deploy)
app.command("list")(deployment.list_deployments)
app.command("ls")(deployment.list_deployments)  # Alias for list


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print(
            """[orange_red1]
    ╭──────────────────────────────────────────────────────────────────────╮
    │         Fastest way to build, prototype and deploy AI Agents.        │
    │                         [bold][link=https://celesto.ai]by Celesto AI[/link][/bold]                                │
    ╰──────────────────────────────────────────────────────────────────────┘
[range_red1]
"""
        )
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
