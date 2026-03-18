"""GET /api/providers endpoint -- list available LLM providers."""

import os
import shutil

from fastapi import APIRouter
from pydantic import BaseModel

from codehive.config import Settings

providers_router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderInfo(BaseModel):
    """Information about a configured LLM provider."""

    name: str
    type: str  # "cli" or "api"
    available: bool
    reason: str
    default_model: str


def _check_cli_available(cli_name: str) -> tuple[bool, str]:
    """Check if a CLI tool is on PATH. Returns (available, reason)."""
    path = shutil.which(cli_name)
    if path:
        return True, f"CLI found at {path}"
    return False, "CLI not found"


def _check_api_key(key_value: str, provider_label: str) -> tuple[bool, str]:
    """Check if an API key is set. Returns (available, reason)."""
    if key_value:
        return True, "API key set"
    return False, "API key not set"


@providers_router.get("", response_model=list[ProviderInfo])
async def list_providers() -> list[ProviderInfo]:
    """Return available providers with their configuration status."""
    settings = Settings()

    # Claude: CLI-based provider
    claude_available, claude_reason = _check_cli_available("claude")

    # Codex: CLI-based provider
    codex_available, codex_reason = _check_cli_available("codex")

    # OpenAI API: key-based provider
    openai_key = (
        settings.openai_api_key
        or os.environ.get("CODEHIVE_OPENAI_API_KEY", "")
        or os.environ.get("OPENAI_API_KEY", "")
    )
    openai_available, openai_reason = _check_api_key(openai_key, "OpenAI")

    # Z.ai: key-based provider
    zai_key = (
        settings.zai_api_key
        or os.environ.get("CODEHIVE_ZAI_API_KEY", "")
        or os.environ.get("ZAI_API_KEY", "")
    )
    zai_available, zai_reason = _check_api_key(zai_key, "Z.ai")

    return [
        ProviderInfo(
            name="claude",
            type="cli",
            available=claude_available,
            reason=claude_reason,
            default_model=settings.default_model,
        ),
        ProviderInfo(
            name="codex",
            type="cli",
            available=codex_available,
            reason=codex_reason,
            default_model="codex-mini-latest",
        ),
        ProviderInfo(
            name="openai",
            type="api",
            available=openai_available,
            reason=openai_reason,
            default_model="codex-mini-latest",
        ),
        ProviderInfo(
            name="zai",
            type="api",
            available=zai_available,
            reason=zai_reason,
            default_model="glm-4.7",
        ),
    ]
