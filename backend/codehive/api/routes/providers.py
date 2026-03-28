"""GET /api/providers endpoint -- list available LLM providers."""

import os
import shutil

from fastapi import APIRouter
from pydantic import BaseModel

from codehive.config import Settings

providers_router = APIRouter(prefix="/api/providers", tags=["providers"])


class ModelInfo(BaseModel):
    """Information about a model available for a provider."""

    id: str
    name: str
    is_default: bool = False


class ProviderInfo(BaseModel):
    """Information about a configured LLM provider."""

    name: str
    type: str  # "cli" or "api"
    available: bool
    reason: str
    models: list[ModelInfo]


# ---------------------------------------------------------------------------
# Model constants per provider (March 2026)
# ---------------------------------------------------------------------------

CLAUDE_MODELS: list[ModelInfo] = [
    ModelInfo(id="claude-sonnet-4-6", name="Claude Sonnet 4.6", is_default=True),
    ModelInfo(id="claude-opus-4-6", name="Claude Opus 4.6"),
    ModelInfo(id="claude-sonnet-4-5", name="Claude Sonnet 4.5"),
    ModelInfo(id="claude-haiku-4-5", name="Claude Haiku 4.5"),
]

OPENAI_MODELS: list[ModelInfo] = [
    ModelInfo(id="gpt-5.4", name="GPT-5.4", is_default=True),
    ModelInfo(id="gpt-5.4-mini", name="GPT-5.4 Mini"),
    ModelInfo(id="o4-mini", name="O4 Mini"),
    ModelInfo(id="o3", name="O3"),
]

CODEX_MODELS: list[ModelInfo] = [
    ModelInfo(id="gpt-5.4", name="GPT-5.4", is_default=True),
    ModelInfo(id="gpt-5.3-codex", name="GPT-5.3 Codex"),
    ModelInfo(id="gpt-5.4-mini", name="GPT-5.4 Mini"),
]

GEMINI_MODELS: list[ModelInfo] = [
    ModelInfo(id="gemini-2.5-flash", name="Gemini 2.5 Flash", is_default=True),
    ModelInfo(id="gemini-2.5-pro", name="Gemini 2.5 Pro"),
    ModelInfo(id="gemini-3.1-pro-preview", name="Gemini 3.1 Pro (Preview)"),
]

COPILOT_MODELS: list[ModelInfo] = [
    ModelInfo(id="default", name="Default", is_default=True),
]

ZAI_MODELS: list[ModelInfo] = [
    ModelInfo(id="claude-sonnet-4-6", name="Claude Sonnet 4.6", is_default=True),
    ModelInfo(id="claude-opus-4-6", name="Claude Opus 4.6"),
]


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

    # Copilot: CLI-based provider
    copilot_available, copilot_reason = _check_cli_available("copilot")

    # Gemini: CLI-based provider
    gemini_available, gemini_reason = _check_cli_available("gemini")

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
            models=CLAUDE_MODELS,
        ),
        ProviderInfo(
            name="codex",
            type="cli",
            available=codex_available,
            reason=codex_reason,
            models=CODEX_MODELS,
        ),
        ProviderInfo(
            name="openai",
            type="api",
            available=openai_available,
            reason=openai_reason,
            models=OPENAI_MODELS,
        ),
        ProviderInfo(
            name="zai",
            type="api",
            available=zai_available,
            reason=zai_reason,
            models=ZAI_MODELS,
        ),
        ProviderInfo(
            name="copilot",
            type="cli",
            available=copilot_available,
            reason=copilot_reason,
            models=COPILOT_MODELS,
        ),
        ProviderInfo(
            name="gemini",
            type="cli",
            available=gemini_available,
            reason=gemini_reason,
            models=GEMINI_MODELS,
        ),
    ]
