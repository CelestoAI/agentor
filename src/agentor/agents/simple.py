from agents.tool import FunctionTool
from litellm import responses


class LLM:
    def __init__(self, model: str, api_key: str):
        self.model = model
        self._api_key = api_key

    def _prepare_tools(self, tools: list[FunctionTool]):
        if not tools:
            return
        json_tools = []
        functions = {}
        for tool in tools:
            functions[tool.name] = tool
            json_tools.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "type": "function",
                    "parameters": {
                        "type": "object",
                        "properties": tool.params_json_schema["properties"],
                        "required": tool.params_json_schema["required"],
                    },
                }
            )
        return json_tools, functions

    def chat(
        self,
        input: str,
        tools: list[FunctionTool] | None = None,
        call_tools: bool = True,
    ):
        json_tools = None
        if tools:
            json_tools, functions = self._prepare_tools(tools)

        response = responses(
            model=self.model,
            input=input,
            api_key=self._api_key,
            tools=json_tools,
        )
        if response.output[-1].type == "function_call" and call_tools:
            tool_name = response.output[-1].function_call.name
            func = functions[tool_name]
            return func(**response.output[-1].function_call.arguments)

        return response
