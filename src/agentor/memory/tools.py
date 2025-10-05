import logging
from typing import Any

from agents import RunContextWrapper, function_tool

from agentor.memory.api import ChatType

logger = logging.getLogger(__name__)


@function_tool
def memory_search(
    ctx: RunContextWrapper[Any], query: str, limit: int = 10
) -> list[str]:
    """
    Search the memory for the most relevant conversations.
    """
    try:
        memory = ctx.context.core.memory
        return memory.search(query, limit)["text"].tolist()
    except Exception as e:
        logger.error(f"Error searching memory: {e}", exc_info=True)
        return []


@function_tool
def memory_get_full_conversation(ctx: RunContextWrapper[Any]) -> list[str]:
    """
    Get the full conversation from the memory.
    """
    try:
        memory = ctx.context.core.memory
        return memory.get_full_conversation()["text"].tolist()
    except Exception as e:
        logger.error(f"Error getting full conversation: {e}", exc_info=True)
        return []


@function_tool
def memory_add(ctx: RunContextWrapper[Any], conversation: ChatType) -> None:
    """Add a conversation to the memory."""
    try:
        memory = ctx.context.core.memory
        memory.add(conversation)
    except Exception as e:
        logger.error(f"Error adding conversation: {e}", exc_info=True)
        return None
