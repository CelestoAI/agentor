import asyncio
from typing import List, Optional, Dict, Any
from agents import Runner

from .agenthub import main_agent, gmail_context


class Zen:
    def __init__(self):
        self.main_agent = main_agent
        self.gmail_context = gmail_context
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
        user_context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_turns: int = 10,
    ) -> str:
        """
        Run an agent with the specified tools and context.

        Args:
            prompt: The user's request/prompt
            tools: List of tool names to enable (e.g., ["search_gmail", "web_search"])
            user_context: Context data (e.g., {"email_user_id": "me"})
            model: Optional model override
            max_turns: Maximum conversation turns

        Returns:
            The agent's response as a string
        """
        # Determine which agent to use based on tools
        agent = self.main_agent
        context = None

        # If any Gmail tool is requested, use the gmail context
        if tools and any(t in self._tools for t in tools):
            context = self.gmail_context

            # Update context with user-provided values
            if user_context:
                if hasattr(context, "user_id") and "email_user_id" in user_context:
                    context.user_id = user_context["email_user_id"]

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
        user_context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_turns: int = 10,
    ) -> str:
        return asyncio.run(self.run(prompt, tools, user_context, model, max_turns))


async def run(
    prompt: str,
    tools: Optional[List[str]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    max_turns: int = 10,
) -> str:
    """
    Run an agent with the specified tools and context.

    Args:
        prompt: The user's request/prompt
        tools: List of tool names to enable (e.g., ["search_gmail", "web_search"])
        user_context: Context data (e.g., {"email_user_id": "me"})
        model: Optional model override
        max_turns: Maximum conversation turns

    Returns:
        The agent's response as a string
    """
    # Determine which agent to use based on tools
    zen = Zen()
    return await zen.run(prompt, tools, user_context, model, max_turns)


def run_sync(
    prompt: str,
    tools: Optional[List[str]] = None,
    user_context: Optional[Dict[str, Any]] = None,
    model: Optional[str] = None,
    max_turns: int = 10,
) -> str:
    """
    Synchronous wrapper for the run function.
    """
    return asyncio.run(run(prompt, tools, user_context, model, max_turns))
