import typer
from fastmcp import FastMCP

app = typer.Typer()


@app.command()
def create_proxy(remote_url: str, name: str | None = None):
    """Create a proxy to a remote MCP server.

    Example:
        agentor create-proxy https://example.com/mcp/ MyProxyServer

    Args:
        remote_url (str): The URL of the remote MCP server.
        name (str | None, optional): The name of the proxy. Defaults to None.

    Returns:
        FastMCP: The proxy server.
    """
    try:
        mcp_server = FastMCP.as_proxy(remote_url, name=name)
        mcp_server.run()
    except Exception as e:
        typer.echo(f"Error creating proxy: {e}", err=True)
        raise typer.Exit(1)
