"""Tests for GET /api/providers endpoint and _build_engine provider routing."""

import os
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    """Clear CODEHIVE_* env vars to get clean settings."""
    for key in list(os.environ):
        if key.startswith("CODEHIVE_"):
            monkeypatch.delenv(key)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


class TestProvidersEndpoint:
    """Tests for the providers route handler."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_list_providers_returns_both(self, monkeypatch):
        """Endpoint returns both anthropic and zai providers."""
        monkeypatch.setenv("CODEHIVE_ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")

        from codehive.api.routes.providers import list_providers

        result = await list_providers()

        assert len(result) == 2
        names = [p.name for p in result]
        assert "anthropic" in names
        assert "zai" in names

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_api_key_set_reflects_env(self, monkeypatch):
        """api_key_set is True when key is set, False when not."""
        monkeypatch.setenv("CODEHIVE_ANTHROPIC_API_KEY", "sk-test")
        # No ZAI key set

        from codehive.api.routes.providers import list_providers

        result = await list_providers()

        anthropic = next(p for p in result if p.name == "anthropic")
        zai = next(p for p in result if p.name == "zai")

        assert anthropic.api_key_set is True
        assert zai.api_key_set is False

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_zai_default_model(self):
        """Z.ai provider default model is glm-4.7."""
        from codehive.api.routes.providers import list_providers

        result = await list_providers()
        zai = next(p for p in result if p.name == "zai")
        assert zai.default_model == "glm-4.7"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_anthropic_default_model(self):
        """Anthropic provider default model is claude-sonnet-4-20250514."""
        from codehive.api.routes.providers import list_providers

        result = await list_providers()
        anthropic = next(p for p in result if p.name == "anthropic")
        assert anthropic.default_model == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_zai_base_url(self):
        """Z.ai provider base URL is correct."""
        from codehive.api.routes.providers import list_providers

        result = await list_providers()
        zai = next(p for p in result if p.name == "zai")
        assert zai.base_url == "https://api.z.ai/api/anthropic"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_anthropic_base_url_default(self):
        """Anthropic provider base URL falls back to api.anthropic.com."""
        from codehive.api.routes.providers import list_providers

        result = await list_providers()
        anthropic = next(p for p in result if p.name == "anthropic")
        assert anthropic.base_url == "https://api.anthropic.com"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_anthropic_custom_base_url(self, monkeypatch):
        """Custom anthropic base_url is reflected."""
        monkeypatch.setenv("CODEHIVE_ANTHROPIC_BASE_URL", "https://my-proxy.com")

        from codehive.api.routes.providers import list_providers

        result = await list_providers()
        anthropic = next(p for p in result if p.name == "anthropic")
        assert anthropic.base_url == "https://my-proxy.com"


class TestBuildEngineProviderRouting:
    """Tests for _build_engine provider selection from session config."""

    @pytest.mark.asyncio
    async def test_zai_provider_uses_zai_credentials(self, monkeypatch):
        """provider=zai uses zai_api_key and zai_base_url."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")
        monkeypatch.setenv("CODEHIVE_ZAI_BASE_URL", "https://api.z.ai/api/anthropic")

        captured_kwargs = {}

        class FakeAsyncAnthropic:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch("anthropic.AsyncAnthropic", FakeAsyncAnthropic):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "zai"}, engine_type="native")
            except Exception:
                pass

        assert captured_kwargs.get("api_key") == "sk-zai-test"
        assert captured_kwargs.get("base_url") == "https://api.z.ai/api/anthropic"

    @pytest.mark.asyncio
    async def test_zai_provider_default_model(self, monkeypatch):
        """provider=zai defaults to glm-4.7 model."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")

        captured_engine_kwargs = {}

        from codehive.engine.native import NativeEngine

        def capturing_init(self_engine, **kwargs):
            captured_engine_kwargs.update(kwargs)

        with (
            patch("anthropic.AsyncAnthropic", MagicMock),
            patch.object(NativeEngine, "__init__", capturing_init),
        ):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "zai"}, engine_type="native")
            except Exception:
                pass

        assert captured_engine_kwargs.get("model") == "glm-4.7"

    @pytest.mark.asyncio
    async def test_zai_provider_custom_model(self, monkeypatch):
        """provider=zai with explicit model uses that model."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")

        captured_engine_kwargs = {}

        from codehive.engine.native import NativeEngine

        def capturing_init(self_engine, **kwargs):
            captured_engine_kwargs.update(kwargs)

        with (
            patch("anthropic.AsyncAnthropic", MagicMock),
            patch.object(NativeEngine, "__init__", capturing_init),
        ):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "zai", "model": "glm-5"}, engine_type="native")
            except Exception:
                pass

        assert captured_engine_kwargs.get("model") == "glm-5"

    @pytest.mark.asyncio
    async def test_zai_provider_no_key_raises_503(self, monkeypatch):
        """provider=zai without API key raises 503."""
        monkeypatch.delenv("CODEHIVE_ZAI_API_KEY", raising=False)
        monkeypatch.delenv("ZAI_API_KEY", raising=False)
        # Ensure clean settings
        for key in list(os.environ):
            if key.startswith("CODEHIVE_ZAI"):
                monkeypatch.delenv(key)

        from fastapi import HTTPException

        from codehive.api.routes.sessions import _build_engine

        with pytest.raises(HTTPException) as exc_info:
            await _build_engine({"provider": "zai"}, engine_type="native")
        assert exc_info.value.status_code == 503
        assert "Z.ai" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_anthropic_provider_default(self, monkeypatch):
        """No provider in config defaults to anthropic."""
        monkeypatch.setenv("CODEHIVE_ANTHROPIC_API_KEY", "sk-ant-test")

        captured_kwargs = {}

        class FakeAsyncAnthropic:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch("anthropic.AsyncAnthropic", FakeAsyncAnthropic):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({}, engine_type="native")
            except Exception:
                pass

        assert captured_kwargs.get("api_key") == "sk-ant-test"

    @pytest.mark.asyncio
    async def test_explicit_anthropic_provider(self, monkeypatch):
        """provider=anthropic uses anthropic credentials."""
        monkeypatch.setenv("CODEHIVE_ANTHROPIC_API_KEY", "sk-ant-explicit")

        captured_kwargs = {}

        class FakeAsyncAnthropic:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch("anthropic.AsyncAnthropic", FakeAsyncAnthropic):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "anthropic"}, engine_type="native")
            except Exception:
                pass

        assert captured_kwargs.get("api_key") == "sk-ant-explicit"
