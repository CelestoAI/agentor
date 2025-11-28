from __future__ import annotations

import asyncio
from typing import Tuple
from uuid import uuid4

import httpx
import typer
from a2a.client import Client, ClientConfig, ClientFactory
from a2a.types import Message, TextPart
from rich.console import Console

app = typer.Typer()
console = Console()
DEFAULT_TIMEOUT_SECONDS = 120.0


async def _connect_client(
    agent: str, timeout: float
) -> Tuple[Client, httpx.AsyncClient]:
    """
    Connect to the remote agent with a ClientConfig that uses an httpx timeout.
    Returns the client and the httpx.AsyncClient to close after the call completes.
    """
    http_client = httpx.AsyncClient(timeout=timeout)
    client_config = ClientConfig(httpx_client=http_client)

    try:
        client = await ClientFactory.connect(agent=agent, client_config=client_config)
        return client, http_client
    except Exception:  # noqa: BLE001
        await http_client.aclose()
        raise


async def _get_card(agent: str, timeout: float):
    client, http_client = await _connect_client(agent, timeout)
    try:
        card = await client.get_card()
        console.print(card.model_dump(mode="json"))
    finally:
        await http_client.aclose()


@app.command()
def get_card(
    agent: str = typer.Option(
        "http://localhost:8000", help="The URL of the agent to connect to"
    ),
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT_SECONDS,
        help="Timeout in seconds for connecting to the agent",
    ),
):
    if timeout <= 0:
        raise typer.BadParameter(
            "Timeout must be greater than zero.", param_name="timeout"
        )
    asyncio.run(_get_card(agent, timeout))


async def _send_message(agent: str, input: str, timeout: float):
    import sys
    import traceback

    http_client = None
    try:
        client, http_client = await _connect_client(agent, timeout)

        message = Message(
            role="user",
            parts=[TextPart(text=input)],
            message_id=str(uuid4()),
            task_id=str(uuid4()),
            context_id=str(uuid4()),
        )
        response_stream = client.send_message(message)

        async for event in response_stream:
            try:
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
                            console.print(
                                f"\n[dim]Task status: {update.status.state}[/dim]"
                            )
            except Exception as e:  # noqa: BLE001
                print(f"\n[ERROR] Failed to process event: {e}", file=sys.stderr)
                print(f"Event type: {type(event)}", file=sys.stderr)
                print(f"Event: {event}", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                raise
    except Exception as e:  # noqa: BLE001
        print(f"\n[ERROR] Stream failed: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
    finally:
        if http_client is not None:
            await http_client.aclose()


@app.command()
def chat(
    agent: str = typer.Option(
        "http://localhost:8000", help="The URL of the agent to connect to"
    ),
    message: str = typer.Option(..., help="The message to send to the agent"),
    timeout: float = typer.Option(
        DEFAULT_TIMEOUT_SECONDS,
        help="Timeout in seconds for connecting to the agent",
    ),
):
    if timeout <= 0:
        raise typer.BadParameter(
            "Timeout must be greater than zero.", param_name="timeout"
        )
    asyncio.run(_send_message(agent, message, timeout))
