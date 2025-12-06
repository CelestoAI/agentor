from typing import Any, Dict

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agentor.a2a import A2AController


@pytest.fixture
def expected_agent_card() -> Dict[str, Any]:
    return {
        "additionalInterfaces": [],
        "capabilities": {
            "extensions": None,
            "pushNotifications": None,
            "stateTransitionHistory": None,
            "streaming": True,
        },
        "defaultInputModes": ["application/json"],
        "defaultOutputModes": [],
        "description": "Agentor is a framework for building, prototyping and deploying AI Agents.",
        "documentationUrl": None,
        "iconUrl": None,
        "name": "Agentor",
        "preferredTransport": "JSONRPC",
        "protocolVersion": "0.3.0",
        "provider": None,
        "security": [],
        "securitySchemes": {},
        "signatures": [],
        "skills": [],
        "url": "http://0.0.0.0:8000",
        "version": "0.0.1",
        "supportsAuthenticatedExtendedCard": False,
    }


def test_a2a_controller(expected_agent_card):
    controller = A2AController()
    app = FastAPI()
    app.include_router(controller)
    client = TestClient(app)
    response = client.get("/.well-known/agent-card.json")
    assert response.status_code == 200
    assert response.json() == expected_agent_card
