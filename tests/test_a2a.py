from agentor.agents.a2a import A2AController
from typing import Dict, Any
import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI


@pytest.fixture
def expected_agent_card() -> Dict[str, Any]:
    return {
        "protocolVersion": "0.3.0",
        "name": "Agentor",
        "description": "Agentor is a framework for building, prototyping and deploying AI Agents.",
        "url": "http://0.0.0.0:8000",
        "preferredTransport": "JSONRPC",
        "additionalInterfaces": [],
        "iconUrl": None,
        "provider": None,
        "version": "0.0.1",
        "documentationUrl": None,
        "capabilities": {
            "streaming": True,
            "statefulness": True,
            "asyncProcessing": True,
            "customData": None,
        },
        "securitySchemes": {},
        "security": [],
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": [],
        "skills": [],
        "supportsAuthenticatedExtendedCard": False,
        "signatures": [],
    }


def test_a2a_controller(expected_agent_card):
    controller = A2AController()
    app = FastAPI()
    app.include_router(controller)
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    assert response.json() == expected_agent_card
