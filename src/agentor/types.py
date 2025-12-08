from typing import Dict, List, Literal, TypedDict


class ToolParameterProperty(TypedDict, total=False):
    type: str
    description: str
    enum: List[str] | None


class ToolParameters(TypedDict):
    type: Literal["object"]
    properties: Dict[str, ToolParameterProperty]
    required: List[str]


class ToolFunction(TypedDict):
    name: str
    description: str
    parameters: ToolParameters


class ToolType(TypedDict):
    type: Literal["function"]
    function: ToolFunction
