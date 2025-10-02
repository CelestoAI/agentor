import asyncio
from typing import List, Optional

from agents import Runner

from .agenthub import main_agent
from .integrations.google.google_agent import create_google_context


class Zen:
    def __init__(self):
        self.main_agent = main_agent
        self._tools = {
            "search_gmail",
            "list_gmail_messages",
            "get_gmail_message",
            "get_gmail_message_body",
            # Calendar tools share the same Google context
            "list_calendar_events",
            "get_calendar_event",
        }

    def available_tools(self) -> List[str]:
        return list(self._tools)

    async def run(
        self,
        prompt: str,
        tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        max_turns: int = 10,
        user_id: Optional[str] = None,
    ) -> str:
        """
        Run an agent with the specified tools and context.

        Args:
            prompt: The user's request/prompt
            tools: List of tool names to enable (e.g., ["search_gmail", "web_search"])
            model: Optional model override
            max_turns: Maximum conversation turns
            user_id: Optional user ID for Google tools context

        Returns:
            The agent's response as a string
        """
        # Determine which agent to use based on tools
        agent = self.main_agent
        context = None

        # If any Gmail tool is requested, create the gmail context
        if tools and any(t in self._tools for t in tools):
            context = create_google_context(user_id=user_id)

        # Override model if specified
        if model:
            agent.model = model

        # Run the agent
        result = await Runner.run(
            agent,
            input=prompt,
            context=context,
            max_turns=max_turns,
        )

        return result.final_output

    def run_sync(
        self,
        prompt: str,
        tools: Optional[List[str]] = None,
        model: Optional[str] = None,
        max_turns: int = 10,
        user_id: Optional[str] = None,
    ) -> str:
        return asyncio.run(self.run(prompt, tools, model, max_turns, user_id))


async def run(
    prompt: str,
    tools: Optional[List[str]] = None,
    model: Optional[str] = None,
    max_turns: int = 10,
    user_id: Optional[str] = None,
) -> str:
    """
    Run an agent with the specified tools and context.

    Args:
        prompt: The user's request/prompt
        tools: List of tool names to enable (e.g., ["search_gmail", "web_search"])
        model: Optional model override
        max_turns: Maximum conversation turns
        user_id: Optional user ID for Google tools context

    Returns:
        The agent's response as a string
    """
    zen = Zen()
    return await zen.run(prompt, tools, model, max_turns, user_id)


def run_sync(
    prompt: str,
    tools: Optional[List[str]] = None,
    model: Optional[str] = None,
    max_turns: int = 10,
    user_id: Optional[str] = None,
) -> str:
    """
    Synchronous wrapper for the run function.
    """
    return asyncio.run(run(prompt, tools, model, max_turns, user_id))
