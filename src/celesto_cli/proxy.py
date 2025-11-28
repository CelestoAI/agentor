from __future__ import annotations

import typer

app = typer.Typer(help="Manage MCP proxy connections.")


@app.command("create-proxy")
def create_proxy(remote_url: str, name: str | None = None):
    """Create a proxy to a remote MCP server."""
    try:
        from fastmcp import FastMCP

        mcp_server = FastMCP.as_proxy(remote_url, name=name)
        mcp_server.run()
    except Exception as exc:  # noqa: BLE001
        typer.echo(f"Error creating proxy: {exc}", err=True)
        raise typer.Exit(1) from exc
