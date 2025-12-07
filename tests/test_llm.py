import pytest

from agentor.core.llm import LLM


def test_llm():
    llm = LLM(
        model="test_model", system_prompt="you're a good bot!", api_key="test-key"
    )
    assert llm._system_prompt == "you're a good bot!"


def test_llm_no_api_key():
    with pytest.raises(ValueError, match="An LLM API key is required to use the LLM"):
        LLM(model="test_model")
