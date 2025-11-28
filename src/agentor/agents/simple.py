from agents.tool import FunctionTool
from litellm import responses


class LLM:
    def __init__(self, model: str, api_key: str):
        self.model = model
        self._api_key = api_key

    def _prepare_tools(self, tools: list[FunctionTool]):
        if not tools:
            return
        tools = []
        for tool in tools:
            tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": {
                        "type": "object",
                        "properties": tool.params_json_schema["properties"],
                        "required": tool.params_json_schema["required"],
                    },
                }
            )
        return tools

    def chat(self, input: str, tools: list[FunctionTool] | None = None):
        if tools is not None:
            json_tools = self._prepare_tools(tools)

        response = responses(
            model=self.model,
            input=input,
            api_key=self._api_key,
            tools=json_tools,
        )
        return response
