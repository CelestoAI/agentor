import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Tuple

from litellm import responses

from agentor.core.tool_convertor import ToolConvertor
from agentor.tool_search import ToolSearch

_LLM_API_KEY_ENV_VAR = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")


@dataclass
class FunctionOutput:
    type: Literal["function_output"]
    tool_output: Any


@dataclass
class LLMResponse:
    outputs: List[FunctionOutput]


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

    def _prepare_tools(
        self, tools: List[ToolConvertor | ToolSearch]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, ToolConvertor]]:
        if not tools:
            return [], {}
        json_tools: List[Dict[str, Any]] = []
        functions: Dict[str, ToolConvertor] = {}
        for tool in tools:
            # Allow passing ToolSearch directly; convert to its wrapped FunctionTool.
            if isinstance(tool, ToolSearch):
                tool = tool.to_function_tool()
            if not isinstance(tool, ToolConvertor):
                raise TypeError(
                    f"Unsupported tool type '{type(tool).__name__}'. Expected ToolConvertor or ToolSearch."
                )
            functions[tool.name] = tool
            json_tools.append(tool.to_llm_function())
        return json_tools, functions

    def chat(
        self,
        input: str,
        tools: List[ToolConvertor] | None = None,
        call_tools: bool = False,
        previous_response_id: str | None = None,
    ):
        json_tools: List[Dict[str, Any]] | None = None
        functions: Dict[str, ToolConvertor] = {}
        if tools:
            json_tools, functions = self._prepare_tools(tools)

        response = responses(
            model=self.model,
            input=input,
            instructions=self._system_prompt,
            api_key=self._api_key,
            tools=json_tools,
            previous_response_id=previous_response_id,
        )
        if response.output[-1].type == "function_call" and call_tools:
            tool_name = response.output[-1].name
            func = functions.get(tool_name)
            if func is None:
                raise ValueError(f"Tool '{tool_name}' not found in provided tools.")

            arguments = response.output[-1].arguments
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as e:
                    logging.warning(
                        f"Failed to decode JSON arguments for tool function '{tool_name}': {e}. Using raw arguments string."
                    )
            return LLMResponse(
                outputs=[
                    FunctionOutput(
                        type="function_output", tool_output=func(**arguments)
                    )
                ]
            )

        return response
