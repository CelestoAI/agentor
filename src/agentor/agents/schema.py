from typing import Optional, List, Dict, Any, Union
from enum import Enum
from dataclasses import dataclass
from pydantic import BaseModel, Field


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


class JSONRPCError(BaseModel):
    """
    JSON-RPC 2.0 Error object.
    Represents an error that occurred during the processing of a request.
    """

    code: int = Field(
        ...,
        description="A number that indicates the error type. Standard error codes: -32700 (Parse error), -32600 (Invalid Request), -32601 (Method not found), -32602 (Invalid params), -32603 (Internal error), -32000 to -32099 (Server error)",
    )
    message: str = Field(..., description="A short description of the error")
    data: Optional[Any] = Field(
        None, description="Additional information about the error"
    )


class JSONRPCRequest(BaseModel):
    """
    JSON-RPC 2.0 Request object.
    A remote procedure call is made by sending a Request to a remote service.
    """

    jsonrpc: str = Field(
        default="2.0",
        description="A string specifying the version of the JSON-RPC protocol. MUST be exactly '2.0'",
    )
    method: str = Field(
        ...,
        description="A string containing the name of the method to be invoked",
        examples=["message/send", "tasks/get"],
    )
    params: Optional[Union[List[Any], Dict[str, Any]]] = Field(
        None,
        description="A structured value that holds the parameter values to be used during the invocation of the method. Can be an array or object",
    )
    id: Optional[Union[str, int]] = Field(
        None,
        description="An identifier established by the client. If omitted, the request is assumed to be a notification",
    )


class JSONRPCResponse(BaseModel):
    """
    JSON-RPC 2.0 Response object.
    When a remote procedure call is made, the service responds with a Response.
    """

    jsonrpc: str = Field(
        default="2.0",
        description="A string specifying the version of the JSON-RPC protocol. MUST be exactly '2.0'",
    )
    result: Optional[Any] = Field(
        None,
        description="The result of the method invocation. Required on success, must not exist if there was an error",
    )
    error: Optional[JSONRPCError] = Field(
        None,
        description="An error object if there was an error invoking the method. Required on error, must not exist if successful",
    )
    id: Union[str, int, None] = Field(
        ...,
        description="The id of the request it is responding to. Must be the same as the value of the id member in the Request",
    )


# A2A Operation Schemas


class MessagePart(BaseModel):
    """A part of a message content."""

    type: str = Field(default="text", description="Type of content part")
    text: Optional[str] = Field(None, description="Text content")


class Message(BaseModel):
    """
    Represents a message being sent to or from an agent.
    """

    messageId: str = Field(..., description="Unique identifier for the message")
    role: str = Field(
        ...,
        description="The role of the message sender",
        examples=["user", "assistant", "system"],
    )
    parts: List[MessagePart] = Field(
        ...,
        description="Array of message content parts",
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata for the message"
    )


class PushNotificationConfig(BaseModel):
    """
    Configuration for the agent to send push notifications for updates after the initial response.
    """

    url: str = Field(
        ...,
        description="The URL endpoint where push notifications should be sent",
    )
    headers: Optional[Dict[str, str]] = Field(
        None, description="Optional headers to include in push notification requests"
    )
    method: Optional[str] = Field(
        default="POST",
        description="HTTP method to use for push notifications",
        examples=["POST", "PUT"],
    )


class MessageSendConfiguration(BaseModel):
    """
    Defines configuration options for a message/send or message/stream request.
    """

    acceptedOutputModes: Optional[List[str]] = Field(
        None,
        description="A list of output MIME types the client is prepared to accept in the response",
        examples=[["text/event-stream", "application/json"]],
    )
    historyLength: Optional[int] = Field(
        None,
        description="The number of most recent messages from the task's history to retrieve in the response",
        ge=0,
    )
    pushNotificationConfig: Optional[PushNotificationConfig] = Field(
        None,
        description="Configuration for the agent to send push notifications for updates after the initial response",
    )
    blocking: Optional[bool] = Field(
        default=False,
        description="If true, the client will wait for the task to complete. The server may reject this if the task is long-running",
    )


class MessageSendParams(BaseModel):
    """
    Defines the parameters for a request to send a message to an agent.
    This can be used to create a new task, continue an existing one, or restart a task.
    """

    message: Message = Field(
        ..., description="The message object being sent to the agent"
    )
    configuration: Optional[MessageSendConfiguration] = Field(
        None, description="Optional configuration for the send request"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Optional metadata for extensions"
    )


class TaskStatusState(str, Enum):
    """Valid task status states."""

    SUBMITTED = "submitted"
    WORKING = "working"
    INPUT_REQUIRED = "input-required"
    COMPLETED = "completed"
    CANCELED = "canceled"
    FAILED = "failed"
    REJECTED = "rejected"
    AUTH_REQUIRED = "auth-required"
    UNKNOWN = "unknown"


class TaskStatus(BaseModel):
    """Status of a task."""

    state: TaskStatusState = Field(
        ...,
        description="Current state of the task",
    )


class Task(BaseModel):
    """
    Represents a task created by an agent in response to a message.
    """

    id: str = Field(..., description="Unique identifier for the task")
    contextId: str = Field(..., description="Context/conversation identifier")
    status: TaskStatus = Field(..., description="Current status of the task")
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional metadata about the task"
    )


class TaskStatusUpdateEvent(BaseModel):
    """
    Represents a status update event for a task during streaming.
    """

    type: str = Field(default="task_status_update", description="Event type identifier")
    taskId: str = Field(..., description="The ID of the task being updated")
    contextId: str = Field(..., description="Context/conversation identifier")
    status: TaskStatus = Field(..., description="Updated status of the task")
    final: bool = Field(
        default=False, description="Whether this is the final status update"
    )


class TaskArtifactUpdateEvent(BaseModel):
    """
    Represents an artifact update event for a task during streaming.
    """

    type: str = Field(
        default="task_artifact_update", description="Event type identifier"
    )
    taskId: str = Field(..., description="The ID of the task being updated")
    contextId: str = Field(..., description="Context/conversation identifier")
    artifact: Dict[str, Any] = Field(..., description="The artifact data being sent")


# A2A Protocol Schemas


class TransportProtocol(str, Enum):
    """Supported transport protocols for agent communication."""

    JSONRPC = "JSONRPC"
    GRPC = "GRPC"
    HTTP_JSON = "HTTP+JSON"


class AgentInterface(BaseModel):
    """Additional supported interface (transport and URL combination)."""

    url: str = Field(..., description="The endpoint URL for this interface")
    transport: str = Field(..., description="The transport protocol for this interface")


class AgentProvider(BaseModel):
    """Information about the agent's service provider."""

    name: Optional[str] = Field(None, description="Provider name")
    url: Optional[str] = Field(None, description="Provider URL")


class AgentCapabilities(BaseModel):
    """Declaration of optional capabilities supported by the agent."""

    streaming: Optional[bool] = Field(
        False, description="Whether the agent supports streaming responses"
    )
    statefulness: Optional[bool] = Field(
        False, description="Whether the agent maintains state across requests"
    )
    asyncProcessing: Optional[bool] = Field(
        False, description="Whether the agent supports asynchronous processing"
    )
    customData: Optional[Dict[str, Any]] = Field(
        None, description="Additional custom capabilities"
    )


class SecurityScheme(BaseModel):
    """
    Security scheme definition following OpenAPI 3.0 Security Scheme Object.
    """

    type: str = Field(
        ...,
        description="The type of security scheme (e.g., 'apiKey', 'http', 'oauth2', 'openIdConnect')",
    )
    description: Optional[str] = Field(
        None, description="A description of the security scheme"
    )
    name: Optional[str] = Field(
        None,
        description="The name of the header, query or cookie parameter (for apiKey)",
    )
    in_: Optional[str] = Field(
        None, alias="in", description="The location of the API key (for apiKey)"
    )
    scheme: Optional[str] = Field(
        None, description="The name of the HTTP Authorization scheme (for http)"
    )
    bearerFormat: Optional[str] = Field(
        None, description="A hint to the client on bearer token format (for http)"
    )
    flows: Optional[Dict[str, Any]] = Field(
        None, description="OAuth flow configuration (for oauth2)"
    )
    openIdConnectUrl: Optional[str] = Field(
        None, description="OpenID Connect URL (for openIdConnect)"
    )


class AgentSkill(BaseModel):
    """A skill or distinct capability that the agent can perform."""

    name: str = Field(
        ..., description="The name of the skill", examples=["search_recipes"]
    )
    description: str = Field(
        ..., description="A human-readable description of what the skill does"
    )
    id: Optional[str] = Field(
        None,
        description="A unique identifier for this skill within the agent. If not provided, will be auto-generated from the name",
        examples=["search_recipes", "send_email", "analyze_data"],
    )
    tags: List[str] = Field(
        default_factory=list,
        description="Tags for categorizing and organizing skills",
        examples=[["search", "cooking"], ["communication", "email"]],
    )
    inputModes: Optional[List[str]] = Field(
        None,
        description="Supported input MIME types for this skill (overrides default)",
    )
    outputModes: Optional[List[str]] = Field(
        None,
        description="Supported output MIME types for this skill (overrides default)",
    )
    parameters: Optional[Dict[str, Any]] = Field(
        None, description="JSON Schema for the skill's parameters"
    )
    examples: Optional[List[Dict[str, Any]]] = Field(
        None, description="Example invocations of the skill"
    )

    def model_post_init(self, __context) -> None:
        """Auto-generate id from name if not provided."""
        if self.id is None:
            # Convert name to snake_case for id
            self.id = (
                self.name.lower()
                .replace(" ", "_")
                .replace("-", "_")
                .replace("'", "")
                .replace('"', "")
            )


class AgentCardSignature(BaseModel):
    """JSON Web Signature computed for an AgentCard."""

    algorithm: str = Field(..., description="The signing algorithm used")
    signature: str = Field(..., description="The signature value")
    keyId: Optional[str] = Field(
        None, description="Identifier for the key used to sign"
    )


class AgentCard(BaseModel):
    """
    The AgentCard is a self-describing manifest for an agent. It provides essential
    metadata including the agent's identity, capabilities, skills, supported
    communication methods, and security requirements.
    """

    protocolVersion: str = Field(
        default="0.3.0",
        description="The version of the A2A protocol this agent supports",
    )

    name: str = Field(
        ...,
        description="A human-readable name for the agent",
        examples=["Recipe Agent"],
    )

    description: str = Field(
        ...,
        description="A human-readable description of the agent, assisting users and other agents in understanding its purpose",
        examples=["Agent that helps users with recipes and cooking."],
    )

    url: str = Field(
        ...,
        description="The preferred endpoint URL for interacting with the agent. This URL MUST support the transport specified by 'preferredTransport'",
        examples=["https://api.example.com/a2a/v1"],
    )

    preferredTransport: Optional[str] = Field(
        default="JSONRPC",
        description="The transport protocol for the preferred endpoint. If not specified, defaults to 'JSONRPC'",
        examples=["JSONRPC", "GRPC", "HTTP+JSON"],
    )

    additionalInterfaces: Optional[List[AgentInterface]] = Field(
        None,
        description="A list of additional supported interfaces (transport and URL combinations)",
    )

    iconUrl: Optional[str] = Field(
        None, description="An optional URL to an icon for the agent"
    )

    provider: Optional[AgentProvider] = Field(
        None, description="Information about the agent's service provider"
    )

    version: str = Field(
        ...,
        description="The agent's own version number. The format is defined by the provider",
        examples=["1.0.0"],
    )

    documentationUrl: Optional[str] = Field(
        None, description="An optional URL to the agent's documentation"
    )

    capabilities: AgentCapabilities = Field(
        ..., description="A declaration of optional capabilities supported by the agent"
    )

    securitySchemes: Optional[Dict[str, SecurityScheme]] = Field(
        None,
        description="A declaration of the security schemes available to authorize requests. Follows the OpenAPI 3.0 Security Scheme Object",
    )

    security: Optional[List[Dict[str, List[str]]]] = Field(
        None,
        description="A list of security requirement objects that apply to all agent interactions",
        examples=[[{"oauth": ["read"]}, {"api-key": [], "mtls": []}]],
    )

    defaultInputModes: List[str] = Field(
        default=["application/json"],
        description="Default set of supported input MIME types for all skills, which can be overridden on a per-skill basis",
    )

    defaultOutputModes: List[str] = Field(
        default=["application/json"],
        description="Default set of supported output MIME types for all skills, which can be overridden on a per-skill basis",
    )

    skills: List[AgentSkill] = Field(
        ...,
        description="The set of skills, or distinct capabilities, that the agent can perform",
    )

    supportsAuthenticatedExtendedCard: Optional[bool] = Field(
        default=False,
        description="If true, the agent can provide an extended agent card with additional details to authenticated users",
    )

    signatures: Optional[List[AgentCardSignature]] = Field(
        None, description="JSON Web Signatures computed for this AgentCard"
    )
