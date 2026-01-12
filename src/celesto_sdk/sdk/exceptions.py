"""
Custom exceptions for the Celesto SDK.

This module defines a hierarchy of exceptions that provide clear, actionable
error messages for different failure scenarios when interacting with the
Celesto API.
"""

from typing import Any


class CelestoError(Exception):
    """Base exception for all Celesto SDK errors.

    All exceptions raised by the SDK inherit from this class, allowing
    users to catch all SDK-related errors with a single except clause.

    Example:
        try:
            client.deployment.list()
        except CelestoError as e:
            print(f"SDK error: {e}")
    """

    def __init__(self, message: str, response: Any = None):
        super().__init__(message)
        self.message = message
        self.response = response

    def __str__(self) -> str:
        return self.message


class CelestoAuthenticationError(CelestoError):
    """Raised when authentication fails (401/403 responses).

    This error occurs when:
    - The API key is missing or invalid
    - The API key has been revoked
    - The API key lacks permission for the requested resource

    Example:
        try:
            client = CelestoSDK("invalid-key")
            client.deployment.list()
        except CelestoAuthenticationError as e:
            print("Please check your API key")
    """

    pass


class CelestoNotFoundError(CelestoError):
    """Raised when a requested resource is not found (404 responses).

    This error occurs when:
    - A connection ID doesn't exist
    - A deployment ID is invalid
    - The requested endpoint doesn't exist

    Example:
        try:
            client.gatekeeper.get_connection("non-existent-id")
        except CelestoNotFoundError as e:
            print(f"Resource not found: {e}")
    """

    pass


class CelestoValidationError(CelestoError):
    """Raised when request validation fails (400/422 responses).

    This error occurs when:
    - Required parameters are missing
    - Parameter values are invalid
    - Request body format is incorrect

    Example:
        try:
            client.deployment.deploy(folder=Path("./invalid"), name="")
        except CelestoValidationError as e:
            print(f"Invalid request: {e}")
    """

    pass


class CelestoRateLimitError(CelestoError):
    """Raised when rate limits are exceeded (429 responses).

    This error includes retry information when available.

    Attributes:
        retry_after: Seconds to wait before retrying (if provided by API)

    Example:
        try:
            client.deployment.list()
        except CelestoRateLimitError as e:
            if e.retry_after:
                time.sleep(e.retry_after)
    """

    def __init__(
        self, message: str, response: Any = None, retry_after: int | None = None
    ):
        super().__init__(message, response)
        self.retry_after = retry_after


class CelestoServerError(CelestoError):
    """Raised when the server encounters an error (5xx responses).

    This error indicates a problem on the Celesto API side.
    Retrying the request after a short delay may succeed.

    Example:
        try:
            client.deployment.list()
        except CelestoServerError as e:
            print("Server error, please try again later")
    """

    pass


class CelestoNetworkError(CelestoError):
    """Raised when a network-level error occurs.

    This error occurs when:
    - Unable to connect to the API server
    - Connection times out
    - DNS resolution fails

    Example:
        try:
            client.deployment.list()
        except CelestoNetworkError as e:
            print("Network error, check your connection")
    """

    pass
