from uuid import uuid4
from a2a.client import ClientFactory
from a2a.types import Message, TextPart
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


async def _send_message(agent: str, input: str):
    client = await ClientFactory.connect(
        agent=agent,
    )

    message = Message(
        role="user",
        parts=[TextPart(text=input)],
        message_id=str(uuid4()),
        task_id=str(uuid4()),
        context_id=str(uuid4()),
    )
    response_stream = client.send_message(message)

    async for event in response_stream:
        if isinstance(event, Message):
            console.print("[bold green]Response:[/bold green]")
            for part in event.parts:
                if hasattr(part.root, "text"):
                    console.print(part.root.text)
        else:
            task, update = event
            if update is not None:
                if hasattr(update, "artifact") and update.artifact:
                    for part in update.artifact.parts:
                        if hasattr(part.root, "text"):
                            console.print(part.root.text, end="")
                elif hasattr(update, "status"):
                    console.print(f"\n[dim]Task status: {update.status.state}[/dim]")


@app.command()
def send_message(
    agent: str = typer.Option(
        "http://localhost:8000", help="The URL of the agent to connect to"
    ),
    message: str = typer.Option(..., help="The message to send to the agent"),
):
    asyncio.run(_send_message(agent, message))
