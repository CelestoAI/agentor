import os
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, TypedDict

from litellm import responses

_LLM_API_KEY_ENV_VAR = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")


@dataclass
class FunctionOutput:
    type: Literal["function_output"]
    tool_output: Any


@dataclass
class LLMResponse:
    outputs: List[FunctionOutput]


class ToolParameterProperty(TypedDict, total=False):
    type: str
    description: str
    enum: List[str]


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


class LLM:
    def __init__(
        self, model: str, system_prompt: str | None = None, api_key: str | None = None
    ):
        self.model = model
        self._system_prompt = system_prompt
        self._api_key = api_key or _LLM_API_KEY_ENV_VAR
        if self._api_key is None:
            raise ValueError(
                "An LLM API key is required to use the LLM. "
                "Set LLM(api_key=<your_api_key>) or set OPENAI_API_KEY or LLM_API_KEY environment variable."
            )

    def chat(
        self,
        input: str,
        tools: List[ToolType] | None = None,
        tool_choice: Literal[None, "auto", "required"] = "auto",
        previous_response_id: str | None = None,
    ):
        return responses(
            model=self.model,
            input=input,
            instructions=self._system_prompt,
            api_key=self._api_key,
            tools=tools,
            previous_response_id=previous_response_id,
            tool_choice=tool_choice,
        )
