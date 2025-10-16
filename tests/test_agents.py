import pytest
import os
from agentor.agents import Agentor
from agentor.prompts import THINKING_PROMPT, render_prompt

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")


def test_prompt_rendering():
    prompt = render_prompt(
        THINKING_PROMPT,
        query="What is the weather in London?",
    )
    assert prompt is not None
    assert "What is the weather in London?" in prompt


@pytest.mark.skipif(not OPENAI_API_KEY, reason="OpenAI API token not set")
def test_agentor():
    agent = Agentor(
        name="Agentor",
        model="gpt-5-mini",
    )
    result = agent.think("What is the weather in London?")
    assert result is not None
    assert "The weather in London is sunny" in result
