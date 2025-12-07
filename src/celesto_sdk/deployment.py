from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from dotenv.main import DotEnv
from rich.console import Console
from typing_extensions import Annotated

from celesto_sdk.sdk.client import CelestoSDK

console = Console()


def _get_secrets_from_env_file(
    env_file: Optional[str] = None, secret_name: Optional[str] = None
) -> Optional[str]:
    if not env_file:
        env_file = ".env"
    if not secret_name:
        secret_name = "CELESTO_API_KEY"
    dotenv_path = Path(env_file)
    dot_env = DotEnv(dotenv_path, verbose=True, encoding="utf-8")
    return dot_env.get(secret_name)


def _get_api_key(
    api_key: Optional[str] = None,
    ignore_env_file: Optional[bool] = False,
    secret_name: Optional[str] = None,
) -> str:
    """Get API key from argument or environment variable."""
    if not ignore_env_file:
        final_api_key = api_key or _get_secrets_from_env_file(secret_name=secret_name)
    else:
        final_api_key = api_key
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
    return final_api_key


def _resolve_envs(
    folder_path: Path, envs: Optional[str], ignore_env_file: bool
) -> dict[str, str]:
    """Build environment dictionary from .env file and CLI overrides."""
    env_dict: dict[str, str] = {}
    if not ignore_env_file:
        env_file_path = folder_path / ".env"
        if env_file_path.exists():
            dotenv = DotEnv(env_file_path, verbose=True, encoding="utf-8")
            for key, value in dotenv.dict().items():
                if value:
                    env_dict[key] = value

    if envs:
        for pair in envs.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if "=" not in pair:
                console.print(
                    f"❌ [bold red]Error:[/bold red] Invalid env pair: '{pair}'. Expected format: key=value"
                )
                raise typer.Exit(1)
            key, value = pair.split("=", 1)
            env_dict[key.strip()] = value.strip()

    return env_dict


def deploy(
    folder: Annotated[
        str,
        typer.Argument(
            ...,
            help="Path to the folder containing your agent code",
            default_factory=os.getcwd,
        ),
    ],
    name: Annotated[
        str,
        typer.Option(
            ...,
            "--name",
            "-n",
            help="Name for your deployment",
            default_factory=lambda: f"my-agent-{datetime.now().strftime('%Y%m%d%H%M%S')}",
        ),
    ],
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
        None,
        "--api-key",
        "-k",
        help="Celesto API key (or set CELESTO_API_KEY env var)",
    ),
    ignore_env_file: Optional[bool] = typer.Option(
        False,
        "--ignore-env-file",
        "-i",
        help="Ignore environment file",
    ),
):
    """Deploy an agent to the Celesto AI platform.

    It automatically loads the .env file and injects the environment variables into the deployment. To ignore the .env file, use the --ignore-env-file flag.
    """
    # Get API key
    final_api_key = _get_api_key(api_key, ignore_env_file, "CELESTO_API_KEY")

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

    # Parse environment variables
    env_dict = _resolve_envs(folder_path, envs, bool(ignore_env_file))

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

        # Show deployment details
        deployment_id = result.get("id")
        deployment_name = result.get("name")
        status = result.get("status")
        console.print(f"\n[bold]Deployment ID:[/bold] {deployment_id}")
        console.print(f"[bold]Status:[/bold] {status}")

        # Show URL once ready
        if status == "READY":
            if not deployment_name:
                console.print(
                    "[yellow]⚠️ Unable to determine app name; deployment URL unavailable.[/yellow]"
                )
            else:
                cloud_url = (
                    f"https://api.celesto.ai/v1/deploy/apps/{deployment_name}/chat"
                )
                console.print(f"[bold]URL:[/bold] [link={cloud_url}]{cloud_url}[/link]")
        else:
            console.print(
                "[yellow]⏳ Building... Run 'celesto ls' to check status[/yellow]"
            )

    except Exception as e:  # noqa: BLE001
        console.print(f"❌ [bold red]Deployment failed:[/bold red] {e}")
        raise typer.Exit(1) from e


def list_deployments(
    api_key: Optional[str] = typer.Option(
        None, "--api-key", "-k", help="Celesto API key (or set CELESTO_API_KEY env var)"
    ),
):
    """List all deployments."""
    from rich.table import Table

    # Get API key
    final_api_key = _get_api_key(api_key, secret_name="CELESTO_API_KEY")

    # List deployments
    try:
        client = CelestoSDK(final_api_key)
        deployments = client.deployment.list()

        if not deployments:
            console.print("📭 [yellow]No deployments found.[/yellow]")
            return

        # Create a table
        table = Table(
            title="🚀 Deployments", show_header=True, header_style="bold cyan"
        )
        table.add_column("Name", style="green")
        table.add_column("Status", style="cyan")
        table.add_column("Created At", style="magenta")
        table.add_column("URL", style="blue")

        for deployment in deployments:
            # Construct the cloud URL
            deployment_name = deployment.get("name")
            status = deployment.get("status")
            if deployment_name and status == "READY":
                cloud_url = (
                    f"https://api.celesto.ai/v1/deploy/apps/{deployment_name}/chat"
                )
            elif status == "FAILED":
                cloud_url = "-"
            elif status == "READY":
                cloud_url = "Name unavailable"
            else:
                cloud_url = "Pending"

            table.add_row(
                deployment.get("name", "N/A"),
                deployment.get("status", "N/A"),
                deployment.get("created_at", "N/A").split("T")[0]
                if deployment.get("created_at")
                else "N/A",  # Just date
                cloud_url,
            )

        console.print(table)
        console.print(f"\n📊 Total deployments: [bold]{len(deployments)}[/bold]")

    except Exception as e:  # noqa: BLE001
        console.print(f"❌ [bold red]Failed to list deployments:[/bold red] {e}")
        raise typer.Exit(1) from e
