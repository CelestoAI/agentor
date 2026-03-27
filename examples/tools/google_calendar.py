import os

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from agentor import Agentor
from agentor.tools import CalendarTool

CREDS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_calendar_credentials():
    """
    Get Google Calendar credentials.

    On first run: Opens browser for user to approve access (one-time only)
    On subsequent runs: Loads saved credentials from file
    """

    # If credentials already saved, load and return
    if os.path.exists(CREDS_FILE):
        print(f"Loading credentials from {CREDS_FILE}")
        creds = Credentials.from_authorized_user_file(CREDS_FILE)
        return creds

    # First time: Need OAuth setup
    print("No credentials found. Opening browser for authentication...")
    print("(This only happens once)\n")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise ValueError(
            "Environment variables not set:\n"
            "   export GOOGLE_CLIENT_ID=your_client_id\n"
            "   export GOOGLE_CLIENT_SECRET=your_client_secret\n\n"
            "Get these from: https://console.cloud.google.com/"
        )

    # Create OAuth flow with server credentials
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": client_secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": ["http://localhost:8000"],
            }
        },
        scopes=SCOPES,
    )

    # Opens browser automatically, user approves, credentials returned
    print("Browser opening... Please click 'Allow' to authenticate\n")
    creds = flow.run_local_server(port=8000)

    # Save credentials for future use
    with open(CREDS_FILE, "w") as f:
        f.write(creds.to_json())

    print("Authentication successful!")
    print(f"Credentials saved to: {CREDS_FILE}\n")

    return creds


def main() -> None:
    """Run a sample calendar query using authenticated credentials."""
    # Get credentials (auto-handles OAuth on first run)
    creds = get_calendar_credentials()

    # Create agent with calendar tool
    agent = Agentor(
        name="Calendar Agent",
        model="gpt-4o-mini",
        tools=[CalendarTool(credentials=creds)],
        instructions="Use the calendar tool to help with scheduling and event management.",
    )

    # Example request
    result = agent.run("What events do I have tomorrow?")
    print(result.final_output)


if __name__ == "__main__":
    main()
