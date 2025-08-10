import typer
from rich import print
from zerozen import proxy

app = typer.Typer()
app.add_typer(proxy.app)

# Conditionally add chat app - this will fail gracefully if Google creds not set up
try:
    from zerozen import chat

    app.add_typer(chat.app)
except Exception:
    # If chat fails to import due to missing Google credentials, add a placeholder
    @app.command("chat")
    def chat_placeholder():
        """Start the chat interface."""
        print("[red]❌ Chat requires Google credentials setup.[/red]")
        print("[yellow]Run:[/yellow] [bold]zen setup-google[/bold]")
        raise typer.Exit(1)


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
[/bold green]

[bold cyan]🚀 Quick Start:[/bold cyan]
  zen setup-google  # Set up Gmail/Calendar access
  zen chat          # Start chatting with your AI agent

""")
        typer.echo(ctx.get_help())


@app.command("setup-google")
def setup_google(
    credentials_file: str = typer.Option(
        "credentials.json",
        "--credentials-file",
        "-c",
        help="Path to Google OAuth credentials JSON file",
    ),
    user_storage: str = typer.Option(
        "credentials.my_google_account.json",
        "--user-storage",
        "-u",
        help="Where to save user credentials",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-authentication even if credentials exist"
    ),
):
    """Set up Google authentication for Gmail and Calendar access."""
    import os
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text

    console = Console()

    # Check if user credentials already exist
    if os.path.exists(user_storage) and not force:
        console.print(f"✅ Google credentials already exist: {user_storage}")
        console.print("Use --force to re-authenticate")
        return

    # Check if OAuth app credentials exist
    if not os.path.exists(credentials_file):
        console.print(
            Panel.fit(
                Text.from_markup(
                    """
[bold red]❌ Google OAuth App Credentials Missing![/bold red]

[bold]Setup Required:[/bold]
1. Go to [link=https://console.cloud.google.com/]Google Cloud Console[/link]
2. Create/select project
3. Enable Gmail API and Calendar API
4. Create OAuth 2.0 Client ID (Desktop application)
5. Download JSON as '[bold]credentials.json[/bold]'
6. Run this command again!

[dim]Expected file: {file}[/dim]
            """.format(file=credentials_file)
                ),
                title="🔧 Setup Instructions",
                border_style="red",
            )
        )
        return

    # Perform authentication
    console.print("🚀 Starting Google authentication setup...")

    try:
        from zerozen.integrations.google.creds import authenticate_user
        import json

        # Extract client credentials
        with open(credentials_file) as f:
            creds_data = json.load(f)
            client_id = creds_data["installed"]["client_id"]
            client_secret = creds_data["installed"]["client_secret"]

        console.print(f"🔑 Using client_id: {client_id}")

        # Define scopes
        scopes = [
            "openid",
            "https://www.googleapis.com/auth/gmail.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/userinfo.email",
        ]

        console.print("🌐 Opening browser for authentication...")
        console.print("👆 Please complete authentication in your browser")

        # Authenticate user
        creds = authenticate_user(
            client_id=client_id,
            client_secret=client_secret,
            scopes=scopes,
            user_storage_path=user_storage,
            credentials_file=credentials_file,
        )

        console.print(
            Panel.fit(
                Text.from_markup(f"""
[bold green]✅ Authentication Successful![/bold green]

[bold]User:[/bold] {creds.user_id}
[bold]Scopes:[/bold] Gmail, Calendar, User Info
[bold]Saved to:[/bold] {user_storage}

[bold]Next Steps:[/bold]
• Run [bold cyan]zen chat[/bold cyan] to start using Gmail/Calendar features
• Your credentials will be loaded automatically
            """),
                title="🎉 Setup Complete",
                border_style="green",
            )
        )

    except Exception as e:
        console.print(
            Panel.fit(
                Text.from_markup(f"""
[bold red]❌ Authentication Failed![/bold red]

[bold]Error:[/bold] {e}

[bold]Troubleshooting:[/bold]
• Ensure Gmail API and Calendar API are enabled
• Check credentials.json is valid
• Try running the command again
            """),
                title="💥 Error",
                border_style="red",
            )
        )
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
