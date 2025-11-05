from dataclasses import dataclass

# JSON-RPC 2.0 Protocol Schemas


@dataclass(frozen=True)
class JSONRPCErrorCodes:
    """
    JSON-RPC 2.0 error codes as defined in the specification.
    Organized into standard error codes and custom server error codes.
    """

    # Standard JSON-RPC 2.0 Error Codes
    PARSE_ERROR: int = -32700  # Invalid JSON was received by the server
    INVALID_REQUEST: int = -32600  # The JSON sent is not a valid Request object
    METHOD_NOT_FOUND: int = -32601  # The method does not exist / is not available
    INVALID_PARAMS: int = -32602  # Invalid method parameter(s)
    INTERNAL_ERROR: int = -32603  # Internal JSON-RPC error

    # Server Error Codes (custom implementation-defined errors: -32000 to -32099)
    SERVER_ERROR_NOT_IMPLEMENTED: int = (
        -32000
    )  # Method exists but is not implemented yet
    SERVER_ERROR_UNAUTHORIZED: int = -32001  # Authentication required or failed
    SERVER_ERROR_FORBIDDEN: int = -32002  # Authenticated but not authorized
    SERVER_ERROR_RESOURCE_NOT_FOUND: int = -32003  # Requested resource not found
    SERVER_ERROR_TIMEOUT: int = -32004  # Operation timed out


# Singleton instance for easy access
JSONRPCReturnCodes = JSONRPCErrorCodes()
