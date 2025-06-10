import typer
from rich import print


app = typer.Typer()


@app.command()
def main():
    print("""[bold green]
    ╭──────────────╮
    │   ZEROZEN    │
    ╰──────────────╯
        LLMs in
        ZEN mode
""")
