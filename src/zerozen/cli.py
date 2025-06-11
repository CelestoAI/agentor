import typer
from rich import print
from zerozen import proxy


app = typer.Typer()
app.add_typer(proxy.app)


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print("""
[bold green]
    ╭──────────────╮
    │   ZEROZEN    │
    ╰──────────────╯
        LLMs in
        ZEN mode
""")
        typer.echo(ctx.get_help())


if __name__ == "__main__":
    app()
