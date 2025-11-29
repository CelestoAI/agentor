import json
from typing import Any, Dict, List, Tuple
import logging

from litellm import responses

from agentor.agents.tool_convertor import ToolConvertor


class LLM:
    def __init__(self, model: str, api_key: str):
        self.model = model
        self._api_key = api_key

    def _prepare_tools(
        self, tools: List[ToolConvertor]
    ) -> Tuple[List[Dict[str, Any]], Dict[str, ToolConvertor]]:
        if not tools:
            return [], {}
        json_tools: List[Dict[str, Any]] = []
        functions: Dict[str, ToolConvertor] = {}
        for tool in tools:
            if not isinstance(tool, ToolConvertor):
                raise TypeError(
                    f"Unsupported tool type '{type(tool).__name__}'. Expected ToolConvertor."
                )
            functions[tool.name] = tool
            json_tools.append(tool.to_llm_function())
        return json_tools, functions

    def chat(
        self,
        input: str,
        tools: List[ToolConvertor] | None = None,
        call_tools: bool = True,
    ):
        json_tools: List[Dict[str, Any]] | None = None
        functions: Dict[str, ToolConvertor] = {}
        if tools:
            json_tools, functions = self._prepare_tools(tools)

        response = responses(
            model=self.model,
            input=input,
            api_key=self._api_key,
            functions=json_tools,
        )
        if response.output[-1].type == "function_call" and call_tools:
            tool_name = response.output[-1].function_call.name
            func = functions.get(tool_name)
            if func is None:
                raise ValueError(f"Tool '{tool_name}' not found in provided tools.")

            arguments = response.output[-1].function_call.arguments
            if isinstance(arguments, str):
                try:
                    arguments = json.loads(arguments)
                except json.JSONDecodeError as e:
                    logging.warning(f"Failed to decode JSON arguments for tool function '{tool_name}': {e}. Using raw arguments string.")
            return func(**arguments)

        return response
