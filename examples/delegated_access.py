"""Short example for Delegated Access via CelestoSDK.

Prereqs:
- CELESTO_API_KEY set in env
- CELESTO_PROJECT_ID set in env
- Backend running (or set CELESTO_BASE_URL to a reachable API)
"""

import os

from agentor import CelestoSDK


def main() -> None:
    api_key = os.environ.get("CELESTO_API_KEY")
    project_id = os.environ.get("CELESTO_PROJECT_ID")

    if not api_key or not project_id:
        raise SystemExit("CELESTO_API_KEY and CELESTO_PROJECT_ID are required")

    client = CelestoSDK(api_key)

    # Initiate connection (returns oauth_url if authorization is required)
    response = client.delegated_access.connect(
        subject="user:demo",
        provider="google_drive",
        project_id=project_id,
    )
    print("connect:", response)

    # List current connections
    connections = client.delegated_access.list_connections(project_id=project_id)
    print("connections:", connections)

    # List Drive files for the subject (may require completed OAuth flow)
    files = client.delegated_access.list_drive_files(
        project_id=project_id,
        subject="user:demo",
        page_size=10,
        include_folders=True,
    )
    print("drive_files:", files)


if __name__ == "__main__":
    main()
