"""
Type definitions for Celesto SDK responses.

These TypedDict definitions provide better IDE support and type checking
for API responses. They represent the structure of data returned by
the Celesto API.
"""

from typing import List, Literal
from typing_extensions import NotRequired, TypedDict


# ============================================================================
# ToolHub Types
# ============================================================================


class ToolParameter(TypedDict):
    """A parameter for a tool."""

    name: str
    type: str
    description: str
    required: NotRequired[bool]


class ToolInfo(TypedDict):
    """Information about an available tool."""

    name: str
    description: str
    parameters: NotRequired[List[ToolParameter]]


class ToolListResponse(TypedDict):
    """Response from list_tools()."""

    tools: List[ToolInfo]


class WeatherResponse(TypedDict):
    """Response from run_weather_tool()."""

    temperature: NotRequired[float]
    conditions: NotRequired[str]
    humidity: NotRequired[float]
    wind_speed: NotRequired[float]
    error: str | None


# ============================================================================
# Deployment Types
# ============================================================================


class DeploymentInfo(TypedDict):
    """Information about a deployment."""

    id: str
    name: str
    description: NotRequired[str]
    status: Literal["READY", "BUILDING", "FAILED", "STOPPED"]
    created_at: NotRequired[str]
    updated_at: NotRequired[str]


class DeploymentResponse(TypedDict):
    """Response from deploy()."""

    id: str
    name: str
    status: Literal["READY", "BUILDING", "FAILED"]
    message: NotRequired[str]


# ============================================================================
# GateKeeper Types
# ============================================================================


ConnectionStatus = Literal["pending", "authorized", "failed", "revoked"]


class ConnectionResponse(TypedDict):
    """Response from connect()."""

    connection_id: str
    status: ConnectionStatus
    oauth_url: NotRequired[str]
    subject: NotRequired[str]
    provider: NotRequired[str]


class ConnectionInfo(TypedDict):
    """Detailed connection information."""

    connection_id: str
    subject: str
    provider: str
    status: ConnectionStatus
    project_name: str
    created_at: NotRequired[str]


class ConnectionListResponse(TypedDict):
    """Response from list_connections()."""

    connections: List[ConnectionInfo]


class DriveFile(TypedDict):
    """A Google Drive file or folder."""

    id: str
    name: str
    mimeType: str
    size: NotRequired[str]
    modifiedTime: NotRequired[str]
    createdTime: NotRequired[str]
    parents: NotRequired[List[str]]


class DriveFilesResponse(TypedDict):
    """Response from list_drive_files()."""

    files: List[DriveFile]
    next_page_token: NotRequired[str]


class AccessRules(TypedDict):
    """Access rules for a connection."""

    version: int
    allowed_folders: List[str]
    allowed_files: List[str]
    unrestricted: bool


# ============================================================================
# Export all types
# ============================================================================

__all__ = [
    # ToolHub
    "ToolParameter",
    "ToolInfo",
    "ToolListResponse",
    "WeatherResponse",
    # Deployment
    "DeploymentInfo",
    "DeploymentResponse",
    # GateKeeper
    "ConnectionStatus",
    "ConnectionResponse",
    "ConnectionInfo",
    "ConnectionListResponse",
    "DriveFile",
    "DriveFilesResponse",
    "AccessRules",
]
