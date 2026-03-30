import os
import signal
import socket
import subprocess
import time
import json

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

from agentor import Agentor
from agentor.tools import CalendarTool

CREDS_FILE = "credentials.json"
SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _kill_port_8000():
    """Kill any process using port 8000 to avoid 'Address already in use' errors."""
    try:
        # Use lsof to find process using port 8000
        result = subprocess.run(
            ["lsof", "-i", ":8000", "-t"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if result.stdout.strip():
            pids = result.stdout.strip().split()
            for pid in pids:
                try:
                    os.kill(int(pid), signal.SIGKILL)
                except (ValueError, ProcessLookupError):
                    pass
        # Wait for OS to fully release the port
        time.sleep(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        # lsof not available or timeout - continue anyway
        pass


def get_calendar_credentials():
    """
    Get Google Calendar credentials.

    On first run: Opens browser for user to approve access (one-time only)
    On subsequent runs: Loads saved credentials from file
    """

    # If credentials already saved, load and return
    if os.path.exists(CREDS_FILE):
        print(f"Loading credentials from {CREDS_FILE}")
        try:
            creds = Credentials.from_authorized_user_file(CREDS_FILE)
            if creds.valid:
                return creds

            if creds.expired and creds.refresh_token:
                print("Refreshing expired credentials...")
                try:
                    creds.refresh(Request())
                    with open(CREDS_FILE, "w") as f:
                        f.write(creds.to_json())
                    return creds
                except RefreshError as exc:
                    print(f"Failed to refresh credentials: {exc}")
                    print("Re-running OAuth consent flow...")
            else:
                print("Saved credentials are invalid. Re-running OAuth consent flow...")
        except ValueError as e:
            print(f"Credentials file is invalid: {e}")
            print("Removing invalid credentials file...")
            os.remove(CREDS_FILE)
            print("Re-running OAuth consent flow...")

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
    # Kill any existing process on port 8000
    _kill_port_8000()
    
    # Retry loop for port binding (in case OS hasn't fully released it)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Request offline access to get refresh_token
            creds = flow.run_local_server(port=8000, access_type="offline", prompt="consent")
            break
        except OSError as e:
            if attempt < max_retries - 1:
                print(f"Port binding failed (attempt {attempt + 1}/{max_retries}): {e}")
                print("Retrying in 2 seconds...")
                time.sleep(2)
                _kill_port_8000()
            else:
                raise

    # Save credentials for future use
    print("\nVerifying credentials...")
    creds_data = json.loads(creds.to_json())
    
    if "refresh_token" not in creds_data or not creds_data.get("refresh_token"):
        print("⚠️  Warning: No refresh token received. This might be because:")
        print("  - You previously granted access to this app")
        print("  - Google didn't include a refresh token in this flow")
        print("\nTrying to get refresh token by requesting re-consent...")
        print("Please delete credentials.json and run again to complete OAuth with offline access.\n")
        # Still save what we have
    
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
        model="gpt-5.4-mini",
        tools=[CalendarTool(credentials=creds)],
        instructions="Use the calendar tool to help with scheduling and event management.",
    )

    # Example request
    result = agent.run("What events do I have tomorrow?")
    print(result.final_output)


if __name__ == "__main__":
    main()
