import pytest
from unittest.mock import Mock, patch, AsyncMock

# Import agents - test mode detection handles the mocking automatically
from agentor import agents


@pytest.fixture
def mock_runner_result():
    """Mock runner result with final output."""
    result = Mock()
    result.final_output = "Test response from agent"
    return result


@pytest.fixture
def mock_main_agent():
    """Mock main agent."""
    agent = Mock()
    agent.model = "gpt-4o"
    return agent


@pytest.fixture
def mock_gmail_context():
    """Mock Gmail context."""
    context = Mock()
    context.user_id = "local"
    return context


class TestAgentsRun:
    """Test cases for the agents.run function."""

    @pytest.mark.asyncio
    async def test_run_basic_prompt(self, mock_runner_result, mock_main_agent):
        """Test basic run with just a prompt."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with patch("agentor.agents.main_agent", mock_main_agent):
                result = await agents.run("Hello, how are you?")

                assert result == "Test response from agent"
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args[1]["input"] == "Hello, how are you?"
                assert call_args[1]["max_turns"] == 10
                assert call_args[1]["context"] is None

    @pytest.mark.asyncio
    async def test_run_with_gmail_tools(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        """Test run with Gmail tools specified."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ),
            ):
                result = await agents.run(
                    "Find emails from Stripe",
                    tools=["search_gmail"],
                )

                assert result == "Test response from agent"
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args[1]["context"] == mock_gmail_context

    @pytest.mark.asyncio
    async def test_run_with_model_override(self, mock_runner_result, mock_main_agent):
        """Test run with model override."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with patch("agentor.agents.main_agent", mock_main_agent):
                result = await agents.run("Hello", model="gpt-3.5-turbo", max_turns=5)

                assert result == "Test response from agent"
                assert mock_main_agent.model == "gpt-3.5-turbo"
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args[1]["max_turns"] == 5

    @pytest.mark.asyncio
    async def test_run_without_user_id_specified(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        """Test run with Gmail tools but no user_id parameter."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ) as mock_create_context,
            ):
                result = await agents.run("Find emails", tools=["search_gmail"])

                assert result == "Test response from agent"
                # Should create context with user_id=None (default)
                mock_create_context.assert_called_once_with(user_id=None)

    @pytest.mark.asyncio
    async def test_run_with_custom_user_id(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        """Test run with Gmail tools and custom user_id."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ) as mock_create_context,
            ):
                result = await agents.run(
                    "Find emails",
                    tools=["search_gmail"],
                    user_id="custom_user_123",
                )

                assert result == "Test response from agent"
                # Should create context with the specified user_id
                mock_create_context.assert_called_once_with(user_id="custom_user_123")


class TestAgentsRunSync:
    """Test cases for the agents.run_sync function."""

    def test_run_sync_basic(self, mock_runner_result, mock_main_agent):
        """Test synchronous wrapper function."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with patch("agentor.agents.main_agent", mock_main_agent):
                result = agents.run_sync("Hello, world!")

                assert result == "Test response from agent"
                mock_runner.assert_called_once()

    def test_run_sync_with_all_params(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        """Test synchronous wrapper with all parameters."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ),
            ):
                result = agents.run_sync(
                    prompt="Find emails",
                    tools=["search_gmail"],
                    model="gpt-4",
                    max_turns=3,
                    user_id="test_user",
                )

                assert result == "Test response from agent"
                assert mock_main_agent.model == "gpt-4"
                mock_runner.assert_called_once()
                call_args = mock_runner.call_args
                assert call_args[1]["max_turns"] == 3


class TestAgentsIntegration:
    """Integration-style tests with more complex scenarios."""

    @pytest.mark.asyncio
    async def test_multiple_tools_with_gmail_priority(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        """Test that Gmail context is used when search_gmail is in tools list."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ),
            ):
                result = await agents.run(
                    "Search emails and web",
                    tools=["web_search", "search_gmail", "other_tool"],
                )

                assert result == "Test response from agent"
                call_args = mock_runner.call_args
                assert call_args[1]["context"] == mock_gmail_context

    @pytest.mark.asyncio
    async def test_non_gmail_tools_only(self, mock_runner_result, mock_main_agent):
        """Test that no Gmail context is used when search_gmail is not in tools."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with patch("agentor.agents.main_agent", mock_main_agent):
                result = await agents.run(
                    "Search the web", tools=["web_search", "other_tool"]
                )

                assert result == "Test response from agent"
                call_args = mock_runner.call_args
                assert call_args[1]["context"] is None

    @pytest.mark.asyncio
    async def test_calendar_tools_use_gmail_context(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        """Calendar tools should also trigger the Google (gmail) context."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ),
            ):
                result = await agents.run(
                    "List my events",
                    tools=["list_calendar_events"],
                )

                assert result == "Test response from agent"
                call_args = mock_runner.call_args
                assert call_args[1]["context"] == mock_gmail_context

    @pytest.mark.asyncio
    async def test_get_calendar_event_uses_context(
        self, mock_runner_result, mock_main_agent, mock_gmail_context
    ):
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with (
                patch("agentor.agents.main_agent", mock_main_agent),
                patch(
                    "agentor.agents.create_google_context",
                    return_value=mock_gmail_context,
                ),
            ):
                result = await agents.run(
                    "Fetch event details",
                    tools=["get_calendar_event"],
                )

                assert result == "Test response from agent"
                call_args = mock_runner.call_args
                assert call_args[1]["context"] == mock_gmail_context

    def test_empty_tools_list(self, mock_runner_result, mock_main_agent):
        """Test behavior with empty tools list."""
        with patch("agentor.agents.Runner.run", new_callable=AsyncMock) as mock_runner:
            mock_runner.return_value = mock_runner_result

            with patch("agentor.agents.main_agent", mock_main_agent):
                result = agents.run_sync("Hello", tools=[])

                assert result == "Test response from agent"
                call_args = mock_runner.call_args
                assert call_args[1]["context"] is None
