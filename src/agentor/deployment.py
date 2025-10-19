import os
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from agentor.sdk.client import CelestoSDK

app = typer.Typer(help="Agentor CLI - Deploy and manage AI agents")
console = Console()


@app.command()
def deploy(
    folder: str = typer.Option(
        ..., "--folder", "-f", help="Path to the folder containing your agent code"
    ),
    name: str = typer.Option(..., "--name", "-n", help="Name for your deployment"),
    description: Optional[str] = typer.Option(
        None, "--description", "-d", help="Description of your agent"
    ),
    envs: Optional[str] = typer.Option(
        None,
        "--envs",
        "-e",
        help='Environment variables as comma-separated key=value pairs (e.g., "API_KEY=xyz,DEBUG=true")',
    ),
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="Celesto API key (or set CELESTO_API_KEY env var)"
    ),
):
    """Deploy an agent to Celesto."""
    # Get API key
    final_api_key = api_key or os.environ.get("CELESTO_API_KEY")
    if not final_api_key:
        console.print("❌ [bold red]Error:[/bold red] API key not found.")
        console.print(
            "Please provide it via [bold]--api-key[/bold] or set [bold]CELESTO_API_KEY[/bold] environment variable."
        )
        console.print("\n[bold cyan]To get your API key:[/bold cyan]")
        console.print("1. Log in to https://celesto.ai")
        console.print("2. Navigate to Settings → Security")
        console.print("3. Copy your API key")
        raise typer.Exit(1)

    # Parse environment variables
    env_dict = {}
    if envs:
        for pair in envs.split(","):
            pair = pair.strip()
            if "=" not in pair:
                console.print(
                    f"❌ [bold red]Error:[/bold red] Invalid env pair: '{pair}'. Expected format: key=value"
                )
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            env_dict[key.strip()] = value.strip()

    # Validate folder path
    folder_path = Path(folder).resolve()
    if not folder_path.exists():
        console.print(
            f"❌ [bold red]Error:[/bold red] Folder '{folder_path}' does not exist."
        )
        raise typer.Exit(1)
    if not folder_path.is_dir():
        console.print(
            f"❌ [bold red]Error:[/bold red] '{folder_path}' is not a directory."
        )
        raise typer.Exit(1)

    # Deploy
    try:
        console.print(
            f"🚀 [bold cyan]Deploying[/bold cyan] '{name}' from {folder_path}..."
        )
        client = CelestoSDK(final_api_key)
        result = client.deployment.deploy(
            folder=folder_path, name=name, description=description, envs=env_dict
        )
        console.print("✅ [bold green]Deployment successful![/bold green]")
        console.print(f"📦 Result: {result}")
    except Exception as e:
        console.print(f"❌ [bold red]Deployment failed:[/bold red] {e}")
        raise typer.Exit(1)


def main():
    """CLI entrypoint."""
    app()


if __name__ == "__main__":
    app()
