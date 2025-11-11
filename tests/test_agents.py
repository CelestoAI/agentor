from agentor.agents import Agentor
from agentor.prompts import THINKING_PROMPT, render_prompt
from unittest.mock import patch


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
