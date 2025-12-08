import os
from typing import List, Literal

import litellm

from agentor.types import ToolType

_LLM_API_KEY_ENV_VAR = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")


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
        input: str | list[dict],
        tools: List[ToolType] | None = None,
        tool_choice: Literal[None, "auto", "required"] = "auto",
        previous_response_id: str | None = None,
    ):
        return litellm.responses(
            model=self.model,
            input=input,
            instructions=self._system_prompt,
            api_key=self._api_key,
            tools=tools,
            previous_response_id=previous_response_id,
            tool_choice=tool_choice,
        )

    async def achat(
        self,
        input: str | list[dict],
        tools: List[ToolType] | None = None,
        tool_choice: Literal[None, "auto", "required"] = "auto",
        previous_response_id: str | None = None,
    ):
        return await litellm.aresponses(
            model=self.model,
            input=input,
            instructions=self._system_prompt,
            api_key=self._api_key,
            tools=tools,
            previous_response_id=previous_response_id,
            tool_choice=tool_choice,
        )
