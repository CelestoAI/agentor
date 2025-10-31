from fastapi import APIRouter
from pydantic import BaseModel


class AgentCard(BaseModel):
    name: str
    description: str
    url: str
    icon: str


router = APIRouter(prefix="/a2a")


@router.get("/.well-known/agent-card.json")
def agent_card():
    return {
        "name": "Agentor",
        "description": "Agentor is a tool for building and deploying AI Agents.",
        "url": "https://agentor.ai",
        "icon": "https://agentor.ai/icon.png",
    }
