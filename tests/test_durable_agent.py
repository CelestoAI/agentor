import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentor.durable import DurableAgent
from agentor.tools.base import BaseTool, capability


# Mock litellm to avoid real API calls
@pytest.fixture
def mock_litellm():
    with patch("agentor.durable.durable_agent.litellm") as mock:
        yield mock


@pytest.fixture
def clean_runs_dir():
    runs_dir = Path("test_runs")
    if runs_dir.exists():
        shutil.rmtree(runs_dir)
    yield runs_dir
    if runs_dir.exists():
        shutil.rmtree(runs_dir)


def test_new_run(mock_litellm, clean_runs_dir):
    # Setup mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Hello there!"
    # Use attribute access
    mock_response.choices[0].message.tool_calls = None
    mock_response.model_dump.return_value = {
        "choices": [{"message": {"content": "Hello there!"}}]
    }
    mock_litellm.completion.return_value = mock_response

    # Need to pass list or dict. testing dict here
    agent = DurableAgent(model="gpt-4-mini", tools={}, runs_dir=str(clean_runs_dir))

    result = agent.run("Hi")

    assert result.status == "completed"
    assert result.final_answer == "Hello there!"
    assert len(result.events) >= 3

    run_file = clean_runs_dir / f"{result.run_id}.jsonl"
    assert run_file.exists()


def test_resume_run(mock_litellm, clean_runs_dir):
    run_id = "test_resume"
    runs_dir = clean_runs_dir
    runs_dir.mkdir(parents=True, exist_ok=True)

    log_path = runs_dir / f"{run_id}.jsonl"
    with log_path.open("w") as f:
        f.write(
            json.dumps(
                {
                    "run_id": run_id,
                    "step_index": 0,
                    "type": "user_message",
                    "timestamp": "2025-01-01T00:00:00Z",
                    "payload": {"content": "Hi"},
                }
            )
            + "\n"
        )

    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Resumed Hello!"
    mock_response.choices[0].message.tool_calls = None
    mock_response.model_dump.return_value = {
        "choices": [{"message": {"content": "Resumed Hello!"}}]
    }
    mock_litellm.completion.return_value = mock_response

    agent = DurableAgent(model="gpt-4-mini", tools={}, runs_dir=str(clean_runs_dir))

    result = agent.run(run_id=run_id)

    assert result.status == "completed"
    assert result.final_answer == "Resumed Hello!"


def test_basetool_support(mock_litellm, clean_runs_dir):
    class MyTool(BaseTool):
        name = "my_tool"
        description = "A test tool"

        @capability
        def shout(self, text: str):
            return text.upper() + "!"

    tool_instance = MyTool()

    # 1. LLM calls tool
    msg1 = MagicMock()
    msg1.content = None
    tc = MagicMock()
    tc.id = "call_999"
    tc.function.name = (
        "shout"  # BaseTool capabilities are registered by function name usually?
    )
    # Wait, BaseTool.to_openai_function loops through attrs. if capability decorator is used,
    # function_tool creates a FunctionTool.
    # Agents library's function_tool uses the function name if name_override is not provided.
    # So "shout" is correct.
    tc.function.arguments = '{"text": "hello"}'
    msg1.tool_calls = [tc]

    msg2 = MagicMock()
    msg2.content = "HELLO!"
    msg2.tool_calls = None

    resp1 = MagicMock()
    resp1.choices = [MagicMock(message=msg1)]
    resp1.model_dump.return_value = {
        "choices": [
            {
                "message": {
                    "tool_calls": [
                        {
                            "id": "call_999",
                            "function": {
                                "name": "shout",
                                "arguments": '{"text": "hello"}',
                            },
                        }
                    ]
                }
            }
        ]
    }

    resp2 = MagicMock()
    resp2.choices = [MagicMock(message=msg2)]
    resp2.model_dump.return_value = {"choices": [{"message": {"content": "HELLO!"}}]}

    mock_litellm.completion.side_effect = [resp1, resp2]

    # Pass generic list with BaseTool
    agent = DurableAgent(
        model="gpt-4-mini", tools=[tool_instance], runs_dir=str(clean_runs_dir)
    )

    # Verify schema was generated
    assert len(agent.tool_schemas) == 1
    assert agent.tool_schemas[0]["function"]["name"] == "shout"
    # Ensure parameter schema is present (assuming core lib does it)
    props = agent.tool_schemas[0]["function"]["parameters"]["properties"]
    assert "text" in props

    result = agent.run("Shout hello")

    assert result.status == "completed"
    assert result.final_answer == "HELLO!"

    tool_results = [e for e in result.events if e["type"] == "tool_result"]
    assert len(tool_results) == 1
    assert tool_results[0]["payload"]["output"] == "HELLO!"
