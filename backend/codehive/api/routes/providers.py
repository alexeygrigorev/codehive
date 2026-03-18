"""GET /api/providers endpoint -- list available LLM providers."""

import os

from fastapi import APIRouter
from pydantic import BaseModel

from codehive.config import Settings

providers_router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    """Information about a configured LLM provider."""

    name: str
    base_url: str
    api_key_set: bool
    default_model: str


@providers_router.get("", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    """Return available providers with their configuration status."""
    settings = Settings()

    anthropic_key_set = bool(
        settings.anthropic_api_key
        or os.environ.get("CODEHIVE_ANTHROPIC_API_KEY", "")
        or os.environ.get("ANTHROPIC_API_KEY", "")
    )
    zai_key_set = bool(
        settings.zai_api_key
        or os.environ.get("CODEHIVE_ZAI_API_KEY", "")
        or os.environ.get("ZAI_API_KEY", "")
    )
    openai_key_set = bool(
        settings.openai_api_key
        or os.environ.get("CODEHIVE_OPENAI_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
    )

    anthropic_base = settings.anthropic_base_url or "https://api.anthropic.com"
    openai_base = settings.openai_base_url or "https://api.openai.com"

    return [
        ProviderInfo(
            name="anthropic",
            base_url=anthropic_base,
            api_key_set=anthropic_key_set,
            default_model=settings.default_model,
        ),
        ProviderInfo(
            name="zai",
            base_url=settings.zai_base_url,
            api_key_set=zai_key_set,
            default_model="glm-4.7",
        ),
        ProviderInfo(
            name="openai",
            base_url=openai_base,
            api_key_set=openai_key_set,
            default_model="codex-mini-latest",
        ),
    ]
