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
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


class TestProvidersEndpoint:
    """Tests for the providers route handler."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_list_providers_returns_all_six(self):
        """Endpoint returns claude, codex, openai, zai, copilot, and gemini providers."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        assert len(result) == 6
        names = [p.name for p in result]
        assert "claude" in names
        assert "codex" in names
        assert "openai" in names
        assert "zai" in names
        assert "copilot" in names
        assert "gemini" in names

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_claude_available_when_cli_found(self):
        """Claude is available when claude CLI is on PATH."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.side_effect = lambda name: (
                "/usr/bin/claude" if name == "claude" else None
            )
            result = await list_providers()

        claude = next(p for p in result if p.name == "claude")
        assert claude.available is True
        assert claude.type == "cli"
        assert "CLI found" in claude.reason

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_claude_unavailable_when_cli_missing(self):
        """Claude is unavailable when claude CLI is not on PATH."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        claude = next(p for p in result if p.name == "claude")
        assert claude.available is False
        assert claude.reason == "CLI not found"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_codex_available_when_cli_found(self):
        """Codex is available when codex CLI is on PATH."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.side_effect = lambda name: (
                "/usr/bin/codex" if name == "codex" else None
            )
            result = await list_providers()

        codex = next(p for p in result if p.name == "codex")
        assert codex.available is True
        assert codex.type == "cli"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_codex_unavailable_when_cli_missing(self):
        """Codex is unavailable when codex CLI is not on PATH."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        codex = next(p for p in result if p.name == "codex")
        assert codex.available is False
        assert codex.reason == "CLI not found"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_zai_available_when_key_set(self, monkeypatch):
        """Z.ai is available when API key is set."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")

        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        zai = next(p for p in result if p.name == "zai")
        assert zai.available is True
        assert zai.type == "api"
        assert zai.reason == "API key set"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_zai_unavailable_when_key_missing(self):
        """Z.ai is unavailable when API key is not set."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        zai = next(p for p in result if p.name == "zai")
        assert zai.available is False
        assert zai.reason == "API key not set"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_openai_available_when_key_set(self, monkeypatch):
        """OpenAI API is available when API key is set."""
        monkeypatch.setenv("CODEHIVE_OPENAI_API_KEY", "sk-openai-test")

        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        openai_prov = next(p for p in result if p.name == "openai")
        assert openai_prov.available is True
        assert openai_prov.type == "api"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_openai_unavailable_when_key_missing(self):
        """OpenAI API is unavailable when API key is not set."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        openai_prov = next(p for p in result if p.name == "openai")
        assert openai_prov.available is False
        assert openai_prov.reason == "API key not set"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_provider_info_has_type_field(self):
        """Each provider has a type field (cli or api)."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        for p in result:
            assert p.type in ("cli", "api")


class TestModelListsPerProvider:
    """Tests for the model lists returned per provider."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_each_provider_has_nonempty_models(self):
        """Every provider has at least one model."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        assert len(result) == 6
        for p in result:
            assert len(p.models) > 0, f"{p.name} has no models"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_each_provider_has_exactly_one_default(self):
        """Each provider has exactly one model with is_default=True."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        for p in result:
            defaults = [m for m in p.models if m.is_default]
            assert len(defaults) == 1, f"{p.name} has {len(defaults)} default models"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_claude_models(self):
        """Claude has 4 models with correct IDs; default is claude-sonnet-4-6."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        claude = next(p for p in result if p.name == "claude")
        assert len(claude.models) == 4
        ids = [m.id for m in claude.models]
        assert "claude-sonnet-4-6" in ids
        assert "claude-opus-4-6" in ids
        assert "claude-sonnet-4-5" in ids
        assert "claude-haiku-4-5" in ids
        default = next(m for m in claude.models if m.is_default)
        assert default.id == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_openai_models(self):
        """OpenAI has 4 models with correct IDs; default is gpt-5.4."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        openai_prov = next(p for p in result if p.name == "openai")
        assert len(openai_prov.models) == 4
        ids = [m.id for m in openai_prov.models]
        assert "gpt-5.4" in ids
        assert "gpt-5.4-mini" in ids
        assert "o4-mini" in ids
        assert "o3" in ids
        default = next(m for m in openai_prov.models if m.is_default)
        assert default.id == "gpt-5.4"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_codex_models(self):
        """Codex has 3 models; default is gpt-5.4."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        codex = next(p for p in result if p.name == "codex")
        assert len(codex.models) == 3
        default = next(m for m in codex.models if m.is_default)
        assert default.id == "gpt-5.4"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_gemini_models(self):
        """Gemini has 3 models; default is gemini-2.5-flash."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        gemini = next(p for p in result if p.name == "gemini")
        assert len(gemini.models) == 3
        default = next(m for m in gemini.models if m.is_default)
        assert default.id == "gemini-2.5-flash"

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_copilot_models(self):
        """Copilot has 1 model (id=default)."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        copilot = next(p for p in result if p.name == "copilot")
        assert len(copilot.models) == 1
        assert copilot.models[0].id == "default"
        assert copilot.models[0].is_default is True

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_zai_models(self):
        """Z.ai has 4 models; default is glm-5."""
        from codehive.api.routes.providers import list_providers

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.return_value = None
            result = await list_providers()

        zai = next(p for p in result if p.name == "zai")
        assert len(zai.models) == 4
        default = next(m for m in zai.models if m.is_default)
        assert default.id == "glm-5"


class TestFullProviderList:
    """Integration: mock CLIs and keys, verify full provider response."""

    @pytest.mark.asyncio
    @pytest.mark.usefixtures("_isolated_settings")
    async def test_all_providers_mixed_availability(self, monkeypatch):
        """Mock claude/codex on PATH, Z.ai key set, OpenAI key missing."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")

        from codehive.api.routes.providers import list_providers

        def mock_which(name):
            if name == "claude":
                return "/usr/bin/claude"
            if name == "codex":
                return "/usr/bin/codex"
            return None

        with patch("codehive.api.routes.providers.shutil") as mock_shutil:
            mock_shutil.which.side_effect = mock_which
            result = await list_providers()

        assert len(result) == 6

        claude = next(p for p in result if p.name == "claude")
        assert claude.available is True
        assert claude.type == "cli"

        codex = next(p for p in result if p.name == "codex")
        assert codex.available is True
        assert codex.type == "cli"

        openai_prov = next(p for p in result if p.name == "openai")
        assert openai_prov.available is False
        assert openai_prov.type == "api"

        zai = next(p for p in result if p.name == "zai")
        assert zai.available is True
        assert zai.type == "api"


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

        from codehive.engine.zai_engine import ZaiEngine

        def capturing_init(self_engine, **kwargs):
            captured_engine_kwargs.update(kwargs)

        with (
            patch("anthropic.AsyncAnthropic", MagicMock),
            patch.object(ZaiEngine, "__init__", capturing_init),
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

        from codehive.engine.zai_engine import ZaiEngine

        def capturing_init(self_engine, **kwargs):
            captured_engine_kwargs.update(kwargs)

        with (
            patch("anthropic.AsyncAnthropic", MagicMock),
            patch.object(ZaiEngine, "__init__", capturing_init),
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
    async def test_native_engine_defaults_to_zai(self, monkeypatch):
        """ZaiEngine defaults to zai provider (not anthropic)."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-default")

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

        assert captured_kwargs.get("api_key") == "sk-zai-default"

    @pytest.mark.asyncio
    async def test_native_engine_unsupported_provider_raises_400(self, monkeypatch):
        """ZaiEngine with unsupported provider raises 400."""
        from fastapi import HTTPException

        from codehive.api.routes.sessions import _build_engine

        with pytest.raises(HTTPException) as exc_info:
            await _build_engine({"provider": "anthropic"}, engine_type="native")
        assert exc_info.value.status_code == 400
        assert "Unsupported provider" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_codex_engine_type_returns_codex_engine(self, monkeypatch):
        """engine_type=codex returns a CodexEngine instance."""
        monkeypatch.setenv("CODEHIVE_OPENAI_API_KEY", "sk-openai-test")

        captured_kwargs = {}

        class FakeAsyncOpenAI:
            def __init__(self, **kwargs):
                captured_kwargs.update(kwargs)

        with patch("openai.AsyncOpenAI", FakeAsyncOpenAI):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "openai"}, engine_type="codex")
            except Exception:
                pass

        assert captured_kwargs.get("api_key") == "sk-openai-test"

    @pytest.mark.asyncio
    async def test_codex_engine_no_key_raises_503(self, monkeypatch):
        """engine_type=codex without API key raises 503."""
        monkeypatch.delenv("CODEHIVE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        for key in list(os.environ):
            if key.startswith("CODEHIVE_OPENAI"):
                monkeypatch.delenv(key)

        from fastapi import HTTPException

        from codehive.api.routes.sessions import _build_engine

        with pytest.raises(HTTPException) as exc_info:
            await _build_engine({"provider": "openai"}, engine_type="codex")
        assert exc_info.value.status_code == 503
        assert "OpenAI" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_codex_engine_custom_model(self, monkeypatch):
        """engine_type=codex with explicit model uses that model."""
        monkeypatch.setenv("CODEHIVE_OPENAI_API_KEY", "sk-openai-test")

        captured_engine_kwargs = {}

        from codehive.engine.codex import CodexEngine

        def capturing_init(self_engine, **kwargs):
            captured_engine_kwargs.update(kwargs)

        with (
            patch("openai.AsyncOpenAI", MagicMock),
            patch.object(CodexEngine, "__init__", capturing_init),
        ):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "openai", "model": "gpt-4o"}, engine_type="codex")
            except Exception:
                pass

        assert captured_engine_kwargs.get("model") == "gpt-4o"

    @pytest.mark.asyncio
    async def test_codex_engine_default_model(self, monkeypatch):
        """engine_type=codex defaults to codex-mini-latest model."""
        monkeypatch.setenv("CODEHIVE_OPENAI_API_KEY", "sk-openai-test")

        captured_engine_kwargs = {}

        from codehive.engine.codex import CodexEngine

        def capturing_init(self_engine, **kwargs):
            captured_engine_kwargs.update(kwargs)

        with (
            patch("openai.AsyncOpenAI", MagicMock),
            patch.object(CodexEngine, "__init__", capturing_init),
        ):
            from codehive.api.routes.sessions import _build_engine

            try:
                await _build_engine({"provider": "openai"}, engine_type="codex")
            except Exception:
                pass

        assert captured_engine_kwargs.get("model") == "codex-mini-latest"
