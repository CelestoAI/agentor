"""Example for Delegated Access via CelestoSDK GateKeeper API.

Demonstrates:
- Connecting a subject to Google Drive
- Listing connections
- Managing access rules (restrict to specific folders/files)
- Listing Drive files

Prereqs:
- CELESTO_API_KEY set in env
- CELESTO_PROJECT_NAME set in env
"""

import os

from celesto_sdk.sdk import CelestoSDK


def main() -> None:
    api_key = os.environ.get("CELESTO_API_KEY")
    project_name = os.environ.get("CELESTO_PROJECT_NAME")

    if not api_key or not project_name:
        raise SystemExit("CELESTO_API_KEY and CELESTO_PROJECT_NAME are required")

    client = CelestoSDK(api_key)
    subject = "user:demo"

    # 1. Initiate connection (returns oauth_url if authorization is required)
    print("=== Initiating Connection ===")
    response = client.gatekeeper.connect(
        subject=subject,
        provider="google_drive",
        project_name=project_name,
    )
    print(f"Status: {response.get('status')}")
    oauth_url = response.get("oauth_url")
    if oauth_url:
        print(f"OAuth URL: {oauth_url}")
        print("Complete OAuth flow before continuing...")
        return
    connection_id = response.get("connection_id")
    if not connection_id:
        raise SystemExit("No connection_id returned - check OAuth flow")
    print(f"Connection ID: {connection_id}")

    # 2. List current connections
    print("\n=== Listing Connections ===")
    connections = client.gatekeeper.list_connections(project_name=project_name)
    print(f"Total: {connections.get('total', 0)}")
    for conn in connections.get("data", []):
        print(f"  - {conn['id']}: {conn['subject']} ({conn['status']})")
        # Show access rules status
        rules = conn.get("access_rules")
        if rules:
            print(
                f"    Access: {len(rules.get('allowed_folders', []))} folders, "
                f"{len(rules.get('allowed_files', []))} files"
            )
        else:
            print("    Access: Unrestricted")

    # 3. Get access rules for the connection
    print("\n=== Current Access Rules ===")
    rules = client.gatekeeper.get_access_rules(connection_id)
    print(f"Unrestricted: {rules.get('unrestricted')}")
    print(f"Allowed folders: {rules.get('allowed_folders', [])}")
    print(f"Allowed files: {rules.get('allowed_files', [])}")

    # 4. Update access rules (restrict to specific folder)
    # Get folder ID from Google Drive URL: https://drive.google.com/drive/folders/<FOLDER_ID>
    print("\n=== Updating Access Rules ===")
    folder_id = os.environ.get("DEMO_FOLDER_ID")  # Optional: set to test restrictions
    if folder_id:
        updated_rules = client.gatekeeper.update_access_rules(
            connection_id,
            allowed_folders=[folder_id],
            allowed_files=[],
        )
        print(f"Updated! Unrestricted: {updated_rules.get('unrestricted')}")
        print(f"Allowed folders: {updated_rules.get('allowed_folders')}")
    else:
        print("Skipped (set DEMO_FOLDER_ID env var to test)")

    # 5. List Drive files (respects access rules)
    print("\n=== Listing Drive Files ===")
    files = client.gatekeeper.list_drive_files(
        project_name=project_name,
        subject=subject,
        page_size=10,
        include_folders=True,
    )
    print(f"Files returned: {len(files.get('files', []))}")
    for f in files.get("files", [])[:5]:  # Show first 5
        print(f"  - {f.get('name')} ({f.get('mime_type')})")
    if files.get("next_page_token"):
        print("  ... more available (next_page_token present)")

    # 6. Clear access rules (optional - restore unrestricted access)
    # print("\n=== Clearing Access Rules ===")
    # cleared = client.gatekeeper.clear_access_rules(connection_id)
    # print(f"Unrestricted: {cleared.get('unrestricted')}")


if __name__ == "__main__":
    main()
