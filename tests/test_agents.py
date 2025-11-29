from unittest.mock import MagicMock, patch

import pytest

from agentor.agents import Agentor
from agentor.prompts import THINKING_PROMPT, render_prompt


def test_prompt_rendering():
    prompt = render_prompt(
        THINKING_PROMPT,
        query="What is the weather in London?",
    )
    assert prompt is not None
    assert "What is the weather in London?" in prompt


@patch("agentor.agents.core.Runner.run_sync")
def test_agentor(mock_run_sync):
    mock_run_sync.return_value = "The weather in London is sunny"
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        llm_api_key="test",
    )
    result = agent.run("What is the weather in London?")
    assert result is not None
    assert "The weather in London is sunny" in result


@patch("agentor.agents.core.uvicorn.run")
def test_agentor_serve(mock_uvicorn_run):
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        llm_api_key="test",
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
        llm_api_key="test",
    )
    app = agent._create_app("0.0.0.0", 8000)
    assert app is not None
    assert app.router is not None
    assert app.router.routes is not None
    assert len(app.router.routes) == 8


def test_agentor_without_llm_api_key():
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(
            ValueError, match="An LLM API key is required to use the Agentor."
        ):
            Agentor(
                name="Agentor",
                model="gpt-5-mini",
            )


@patch("agentor.agents.core.Runner.run")
@pytest.mark.asyncio
async def test_agentor_batch_prompts(mock_run):
    mock_run.side_effect = [
        MagicMock(final_output="The weather in London is sunny"),
        MagicMock(final_output="The weather in Paris is sunny"),
    ]
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
        llm_api_key="test",
    )
    results = await agent.arun(
        ["What is the weather in London?", "What is the weather in Paris?"]
    )
    assert results is not None
    assert len(results) == 2
    assert results[0].final_output == "The weather in London is sunny"
    assert results[1].final_output == "The weather in Paris is sunny"
