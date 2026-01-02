import logging
from unittest.mock import MagicMock, patch

import openai
import pytest
from agents import ModelSettings

from agentor.core import Agentor
from agentor.prompts import THINKING_PROMPT, render_prompt
from agentor.tools.registry import ToolRegistry


def test_prompt_rendering():
    prompt = render_prompt(
        THINKING_PROMPT,
        query="What is the weather in London?",
    )
    assert prompt is not None
    assert "What is the weather in London?" in prompt


@patch("agentor.core.agent.Runner.run_sync")
def test_agentor(mock_run_sync):
    mock_run_sync.return_value = "The weather in London is sunny"
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        api_key="test",
    )
    result = agent.run("What is the weather in London?")
    assert result is not None
    assert "The weather in London is sunny" in result


@patch("agentor.core.agent.uvicorn.run")
def test_agentor_serve(mock_uvicorn_run):
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        api_key="test",
    )
    agent._create_app = MagicMock()
    agent.serve()
    mock_uvicorn_run.assert_called_once()
    agent._create_app.assert_called_once()
    mock_uvicorn_run.assert_called_with(
        agent._create_app(),
        host="0.0.0.0",
        port=8000,
        log_level="info",
        access_log=True,
    )


def test_agentor_create_app():
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        api_key="test",
    )
    app = agent._create_app("0.0.0.0", 8000)
    assert app is not None
    assert app.router is not None
    assert app.router.routes is not None
    assert len(app.router.routes) == 8


@patch("agentor.core.agent.Runner.run")
@pytest.mark.asyncio
async def test_agentor_batch_prompts(mock_run):
    mock_run.side_effect = [
        MagicMock(final_output="The weather in London is sunny"),
        MagicMock(final_output="The weather in Paris is sunny"),
    ]
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        api_key="test",
    )
    results = await agent.arun(
        ["What is the weather in London?", "What is the weather in Paris?"]
    )
    assert results is not None
    assert len(results) == 2
    assert results[0].final_output == "The weather in London is sunny"
    assert results[1].final_output == "The weather in Paris is sunny"


def test_agentor_from_md(tmp_path, caplog):
    md_content = """---
name: WeatherBot
tools:
  - get_weather
  - missing_tool
model: gpt-4o-mini
temperature: 0.3
---
You are a concise weather assistant."""
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)

    with caplog.at_level(logging.WARNING):
        agent = Agentor.from_md(md_file, api_key="test-key")

    assert agent.name == "WeatherBot"
    assert agent.instructions == "You are a concise weather assistant."
    assert agent.model == "gpt-4o-mini"
    model_settings = agent.agent.model_settings
    assert model_settings is not None
    temperature = getattr(model_settings, "temperature", None)
    if temperature is None and isinstance(model_settings, dict):
        temperature = model_settings.get("temperature")
    assert temperature == 0.3
    assert len(agent.tools) == 1
    assert agent.tools[0] is ToolRegistry.get("get_weather")["tool"]
    assert any("missing_tool" in message for message in caplog.messages)


def test_agentor_from_md_missing_frontmatter(tmp_path):
    md_content = "No frontmatter or metadata block."
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)

    with pytest.raises(ValueError, match="Agent name"):
        Agentor.from_md(md_file, api_key="test-key")


def test_agentor_from_md_invalid_temperature(tmp_path):
    md_content = """---
name: WeatherBot
temperature: not-a-number
---
Be helpful."""
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)

    with pytest.raises(ValueError, match="Temperature"):
        Agentor.from_md(md_file, api_key="test-key")


def test_agentor_from_md_file_not_found(tmp_path):
    non_existent = tmp_path / "missing.md"
    with pytest.raises(FileNotFoundError, match="Markdown file not found"):
        Agentor.from_md(non_existent, api_key="test-key")


def test_agentor_from_md_empty_instructions(tmp_path):
    md_content = """---
name: WeatherBot
---
"""
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)
    with pytest.raises(ValueError, match="instructions are required"):
        Agentor.from_md(md_file, api_key="test-key")


def test_agentor_from_md_tools_as_string(tmp_path, caplog):
    md_content = """---
name: WeatherBot
tools: get_weather, missing_tool
---
You are a helpful assistant."""
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)

    with caplog.at_level(logging.WARNING):
        agent = Agentor.from_md(md_file, api_key="test-key")

    assert agent.name == "WeatherBot"
    assert len(agent.tools) == 1
    assert agent.tools[0] is ToolRegistry.get("get_weather")["tool"]
    assert any("missing_tool" in message for message in caplog.messages)


def test_agentor_from_md_temperature_merged_with_model_settings(tmp_path):
    md_content = """---
name: WeatherBot
temperature: 0.5
---
You are a helpful assistant."""
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)

    # Provide model_settings without temperature - should merge markdown temperature
    model_settings = ModelSettings(top_p=0.9)
    agent = Agentor.from_md(md_file, api_key="test-key", model_settings=model_settings)

    assert agent.agent.model_settings.temperature == 0.5
    assert agent.agent.model_settings.top_p == 0.9


def test_agentor_from_md_temperature_not_overridden(tmp_path):
    md_content = """---
name: WeatherBot
temperature: 0.5
---
You are a helpful assistant."""
    md_file = tmp_path / "agent.md"
    md_file.write_text(md_content)

    # Provide model_settings with temperature - should NOT override with markdown temperature
    model_settings = ModelSettings(temperature=0.8)
    agent = Agentor.from_md(md_file, api_key="test-key", model_settings=model_settings)

    assert agent.agent.model_settings.temperature == 0.8


@pytest.mark.asyncio
@patch("agentor.core.agent.Runner.run")
async def test_arun_with_agent_input_type(mock_run):
    mock_run.return_value = MagicMock(final_output="The weather in London is sunny")
    agent = Agentor(
        name="Test agent",
        api_key="test-key",
    )
    result = await agent.arun(
        [{"role": "user", "content": "What is the weather in London?"}]
    )
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert args[0] is agent.agent
    assert args[1] == [{"role": "user", "content": "What is the weather in London?"}]
    assert result is not None
    assert result.final_output == "The weather in London is sunny"


@pytest.mark.asyncio
@patch("agentor.core.agent.Runner.run")
async def test_arun_with_fallback_on_rate_limit(mock_run):
    """Test that fallback models are used when rate limit error occurs."""
    # First call raises RateLimitError, second call succeeds
    rate_limit_error = openai.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}},
    )
    mock_run.side_effect = [
        rate_limit_error,  # Primary model fails
        MagicMock(final_output="Success with fallback model"),  # Fallback succeeds
    ]

    agent = Agentor(
        name="Test agent",
        model="gpt-5-mini",
        api_key="test-key",
    )
    result = await agent.arun(
        "What is the weather?",
        fallback_models=["gpt-4o-mini"],
    )

    assert mock_run.call_count == 2
    assert result.final_output == "Success with fallback model"


@pytest.mark.asyncio
@patch("agentor.core.agent.Runner.run")
async def test_arun_with_fallback_tries_multiple_models(mock_run):
    """Test that multiple fallback models are tried in order."""
    rate_limit_error = openai.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}},
    )
    mock_run.side_effect = [
        rate_limit_error,  # Primary model fails
        rate_limit_error,  # First fallback fails
        MagicMock(final_output="Success with second fallback"),  # Second fallback succeeds
    ]

    agent = Agentor(
        name="Test agent",
        model="gpt-5-mini",
        api_key="test-key",
    )
    result = await agent.arun(
        "What is the weather?",
        fallback_models=["gpt-4o-mini", "gpt-4o"],
    )

    assert mock_run.call_count == 3
    assert result.final_output == "Success with second fallback"


@pytest.mark.asyncio
@patch("agentor.core.agent.Runner.run")
async def test_arun_raises_when_all_fallbacks_fail(mock_run):
    """Test that original error is raised when all fallback models fail."""
    rate_limit_error = openai.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}},
    )
    mock_run.side_effect = [
        rate_limit_error,  # Primary model fails
        rate_limit_error,  # Fallback also fails
    ]

    agent = Agentor(
        name="Test agent",
        model="gpt-5-mini",
        api_key="test-key",
    )

    with pytest.raises(openai.RateLimitError):
        await agent.arun(
            "What is the weather?",
            fallback_models=["gpt-4o-mini"],
        )


@pytest.mark.asyncio
@patch("agentor.core.agent.Runner.run")
async def test_arun_without_fallback_raises_immediately(mock_run):
    """Test that rate limit error is raised immediately when no fallback models provided."""
    rate_limit_error = openai.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}},
    )
    mock_run.side_effect = rate_limit_error

    agent = Agentor(
        name="Test agent",
        model="gpt-5-mini",
        api_key="test-key",
    )

    with pytest.raises(openai.RateLimitError):
        await agent.arun("What is the weather?")

    assert mock_run.call_count == 1


@pytest.mark.asyncio
@patch("agentor.core.agent.Runner.run")
async def test_arun_batch_with_fallback_on_rate_limit(mock_run):
    """Test that fallback models work with batch processing."""
    rate_limit_error = openai.RateLimitError(
        message="Rate limit exceeded",
        response=MagicMock(status_code=429),
        body={"error": {"message": "Rate limit exceeded"}},
    )
    mock_run.side_effect = [
        MagicMock(final_output="Weather in London"),  # First task succeeds
        rate_limit_error,  # Second task fails
        MagicMock(final_output="Weather in Paris with fallback"),  # Fallback succeeds
    ]

    agent = Agentor(
        name="Test agent",
        model="gpt-5-mini",
        api_key="test-key",
    )
    results = await agent.arun(
        ["What is the weather in London?", "What is the weather in Paris?"],
        fallback_models=["gpt-4o-mini"],
    )

    assert len(results) == 2
    assert results[0].final_output == "Weather in London"
    assert results[1].final_output == "Weather in Paris with fallback"


# Tracing integration tests
@patch("agentor.core.agent.setup_celesto_tracing")
def test_agentor_with_enable_tracing_true(mock_setup_tracing):
    """Test that tracing is enabled when enable_tracing=True and API key is present."""
    with patch.dict(
        "os.environ", {"CELESTO_API_KEY": "test-api-key-123"}, clear=False
    ):
        from agentor.config import CelestoConfig

        # Create new config instance with the env var
        config = CelestoConfig()

        with patch("agentor.core.agent.celesto_config", config):
            agent = Agentor(
                name="TracingAgent",
                model="gpt-5-mini",
                api_key="test",
                enable_tracing=True,
            )

            # Verify setup_celesto_tracing was called
            mock_setup_tracing.assert_called_once()
            call_kwargs = mock_setup_tracing.call_args
            assert "https://api.celesto.ai/v1/traces/ingest" in call_kwargs[1]["endpoint"]
            assert call_kwargs[1]["token"] == "test-api-key-123"


@patch("agentor.core.agent.setup_celesto_tracing")
def test_agentor_with_enable_tracing_missing_api_key(mock_setup_tracing):
    """Test that ValueError is raised when enable_tracing=True but API key is missing."""
    with patch.dict("os.environ", clear=True):
        from agentor.config import CelestoConfig

        config = CelestoConfig()

        with patch("agentor.core.agent.celesto_config", config):
            with pytest.raises(ValueError, match="Celesto API key is required"):
                agent = Agentor(
                    name="TracingAgent",
                    model="gpt-5-mini",
                    api_key="test",
                    enable_tracing=True,
                )

            # Tracing setup should not be called
            mock_setup_tracing.assert_not_called()


@patch("agentor.core.agent.setup_celesto_tracing")
def test_agentor_auto_tracing_enabled(mock_setup_tracing, capsys):
    """Test that auto-tracing is enabled when API key is present and not disabled."""
    with patch.dict(
        "os.environ",
        {"CELESTO_API_KEY": "test-api-key-456", "CELESTO_DISABLE_AUTO_TRACING": "false"},
        clear=False,
    ):
        from agentor.config import CelestoConfig

        config = CelestoConfig()

        with patch("agentor.core.agent.celesto_config", config):
            agent = Agentor(
                name="AutoTracingAgent",
                model="gpt-5-mini",
                api_key="test",
                enable_tracing=False,  # Explicit False, but auto-tracing should still work
            )

            # Verify setup_celesto_tracing was called
            mock_setup_tracing.assert_called_once()

            # Verify the message was printed
            captured = capsys.readouterr()
            assert "auto enabled LLM monitoring and tracing" in captured.out
            assert "https://celesto.ai/observe" in captured.out


@patch("agentor.core.agent.setup_celesto_tracing")
def test_agentor_auto_tracing_disabled(mock_setup_tracing):
    """Test that auto-tracing is disabled when CELESTO_DISABLE_AUTO_TRACING=True."""
    with patch.dict(
        "os.environ",
        {"CELESTO_API_KEY": "test-api-key-789", "CELESTO_DISABLE_AUTO_TRACING": "true"},
        clear=False,
    ):
        from agentor.config import CelestoConfig

        config = CelestoConfig()

        with patch("agentor.core.agent.celesto_config", config):
            agent = Agentor(
                name="NoAutoTracingAgent",
                model="gpt-5-mini",
                api_key="test",
                enable_tracing=False,
            )

            # Tracing should not be set up
            mock_setup_tracing.assert_not_called()


@patch("agentor.core.agent.setup_celesto_tracing")
def test_agentor_auto_tracing_no_api_key(mock_setup_tracing):
    """Test that auto-tracing is not enabled when API key is not present."""
    with patch.dict("os.environ", clear=True):
        from agentor.config import CelestoConfig

        config = CelestoConfig()

        with patch("agentor.core.agent.celesto_config", config):
            agent = Agentor(
                name="NoApiKeyAgent",
                model="gpt-5-mini",
                api_key="test",
                enable_tracing=False,
            )

            # Tracing should not be set up
            mock_setup_tracing.assert_not_called()


@patch("agentor.core.agent.setup_celesto_tracing")
def test_agentor_auto_tracing_error_handling(mock_setup_tracing, caplog):
    """Test that auto-tracing errors are handled gracefully."""
    mock_setup_tracing.side_effect = Exception("Tracing setup failed")

    with patch.dict(
        "os.environ",
        {"CELESTO_API_KEY": "test-api-key-error"},
        clear=False,
    ):
        from agentor.config import CelestoConfig

        config = CelestoConfig()

        with patch("agentor.core.agent.celesto_config", config):
            with caplog.at_level(logging.WARNING):
                # Should not raise exception
                agent = Agentor(
                    name="ErrorHandlingAgent",
                    model="gpt-5-mini",
                    api_key="test",
                    enable_tracing=False,
                )

                # Should log warning
                assert any("Failed to setup Celesto tracing" in message for message in caplog.messages)
