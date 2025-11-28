import typer
from rich import print
from rich.console import Console

from agentor import proxy
from agentor.cli.deployment import deploy, list_deployments

app = typer.Typer()
app.add_typer(proxy.app)

# Add deployment commands at top level
app.command("deploy")(deploy)
app.command("list")(list_deployments)
app.command("ls")(list_deployments)  # Alias for list

console = Console()


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print("""[orange_red1]
    ╭──────────────────────────────────────────────────────────────────────╮
    │         Fastest way to build, prototype and deploy AI Agents.        │
    │                         [bold][link=https://celesto.ai]by Celesto AI[/link][/bold]                                │
    ╰──────────────────────────────────────────────────────────────────────┘
[range_red1]
""")
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
