from agentor.core.llm import LLM


def test_llm():
    llm = LLM(
        model="test_model", system_prompt="you're a good bot!", api_key="test-key"
    )
    assert llm._system_prompt == "you're a good bot!"
