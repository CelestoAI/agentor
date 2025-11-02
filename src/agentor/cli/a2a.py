from a2a.client import ClientFactory
from rich.console import Console
import asyncio
import typer


app = typer.Typer()
console = Console()


async def _get_card(agent: str):
    client = await ClientFactory.connect(
        agent=agent,
    )
    card = await client.get_card()
    console.print(card.model_dump(mode="json"))


@app.command()
def get_card(
    agent: str = typer.Option(
        "http://localhost:8000", help="The URL of the agent to connect to"
    ),
):
    asyncio.run(_get_card(agent))
