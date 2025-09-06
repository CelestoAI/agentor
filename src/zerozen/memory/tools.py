from typing import Any
from agents import RunContextWrapper, function_tool
from zerozen.memory.api import ChatType


@function_tool
def memory_search(
    ctx: RunContextWrapper[Any], query: str, limit: int = 10
) -> list[str]:
    """
    Search the memory for the most relevant conversations.
    """
    memory = ctx.context.memory
    return memory.search(query, limit)["text"].tolist()


@function_tool
def memory_get_full_conversation(ctx: RunContextWrapper[Any]) -> list[str]:
    """
    Get the full conversation from the memory.
    """
    memory = ctx.context.memory
    return memory.get_full_conversation()["text"].tolist()


@function_tool
def memory_add(ctx: RunContextWrapper[Any], conversation: ChatType) -> None:
    """Add a conversation to the memory."""
    memory = ctx.context.memory
    memory.add(conversation)
