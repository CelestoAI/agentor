from typing import Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings


class CelestoConfig(BaseSettings):
    base_url: str = Field(
        alias="CELESTO_BASE_URL", default="https://api.celesto.ai/v1"
    )  # default to Celesto's LLM API
    api_key: Optional[SecretStr] = Field(
        alias="CELESTO_API_KEY", default=None
    )  # default to Celesto's API key


celesto_config = CelestoConfig()
