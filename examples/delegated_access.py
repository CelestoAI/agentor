"""Short example for Delegated Access via CelestoSDK.

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

    # Initiate connection (returns oauth_url if authorization is required)
    response = client.delegated_access.connect(
        subject="user:demo",
        provider="google_drive",
        project_name=project_name,
    )
    print("connect:", response)

    # List current connections
    connections = client.delegated_access.list_connections(project_name=project_name)
    print("connections:", connections)

    # List Drive files for the subject (may require completed OAuth flow)
    files = client.delegated_access.list_drive_files(
        project_name=project_name,
        subject="user:demo",
        page_size=10,
        include_folders=True,
    )
    print("drive_files:", files)


if __name__ == "__main__":
    main()
