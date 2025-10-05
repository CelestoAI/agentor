#!/usr/bin/env python3
import json
import os

from agentor.integrations.google import (
    DEFAULT_GOOGLE_OAUTH_SCOPES,
    GmailService,
    authenticate_user,
    load_user_credentials,
)

# Configuration
CREDENTIALS_FILE = "credentials.json"
USER_CREDS_FILE = "credentials.my_google_account.json"


def main():
    # Check if user credentials exist
    if os.path.exists(USER_CREDS_FILE):
        creds = load_user_credentials(USER_CREDS_FILE)
        print(f"Loaded credentials for: {creds.user_id}")
    else:
        # First time setup
        if not os.path.exists(CREDENTIALS_FILE):
            print("Missing credentials.json - download from Google Cloud Console")
            return

        # Extract client credentials
        with open(CREDENTIALS_FILE) as f:
            creds_data = json.load(f)
            client_id = creds_data["installed"]["client_id"]
            client_secret = creds_data["installed"]["client_secret"]

        # Authenticate user
        creds = authenticate_user(
            client_id=client_id,
            client_secret=client_secret,
            scopes=DEFAULT_GOOGLE_OAUTH_SCOPES,
            user_storage_path=USER_CREDS_FILE,
            credentials_file=CREDENTIALS_FILE,
        )
        print(f"Authenticated: {creds.user_id}")

    # Use Gmail
    gmail = GmailService(creds)
    messages = gmail.search_messages(query="in:inbox", limit=3)
    print(f"Found {len(messages.get('messages', []))} messages")

    if messages.get("messages"):
        msg = gmail.get_message(messages["messages"][0]["id"])
        print(f"Latest: {msg.get('subject', 'No subject')}")


if __name__ == "__main__":
    main()
