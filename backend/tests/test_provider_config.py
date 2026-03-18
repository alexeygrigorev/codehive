"""Tests for LLM provider configuration (issue #84, updated #110)."""

import argparse
import os
import uuid
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from codehive.cli import _resolve_provider, main
from codehive.config import Settings


@pytest.fixture()
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Clear all CODEHIVE_* and provider env vars, point away from real .env."""
    for key in list(os.environ):
        if key.startswith("CODEHIVE_"):
            monkeypatch.delenv(key)
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _run_cli(args: list[str], monkeypatch: pytest.MonkeyPatch) -> tuple[str, int]:
    """Run the CLI with given args, capture stdout, return (output, exit_code)."""
    monkeypatch.setattr("sys.argv", ["codehive"] + args)
    out = StringIO()
    monkeypatch.setattr("sys.stdout", out)
    err = StringIO()
    monkeypatch.setattr("sys.stderr", err)
    try:
        main()
        return out.getvalue(), 0
    except SystemExit as e:
        return out.getvalue() + err.getvalue(), e.code or 0


# ---------------------------------------------------------------------------
# Settings tests
# ---------------------------------------------------------------------------


class TestProviderSettings:
    """Settings has zai_api_key, zai_base_url, default_model fields."""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_zai_api_key_default(self):
        settings = Settings(_env_file=None)
        assert settings.zai_api_key == ""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_zai_base_url_default(self):
        settings = Settings(_env_file=None)
        assert settings.zai_base_url == "https://api.z.ai/api/anthropic"

    @pytest.mark.usefixtures("_isolated_settings")
    def test_default_model_default(self):
        settings = Settings(_env_file=None)
        assert settings.default_model == "claude-sonnet-4-20250514"

    def test_zai_api_key_env_override(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-test")
        settings = Settings()
        assert settings.zai_api_key == "sk-zai-test"

    def test_zai_base_url_env_override(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_ZAI_BASE_URL", "https://custom.z.ai")
        settings = Settings()
        assert settings.zai_base_url == "https://custom.z.ai"

    def test_default_model_env_override(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_DEFAULT_MODEL", "glm-4.7")
        settings = Settings()
        assert settings.default_model == "glm-4.7"

    @pytest.mark.usefixtures("_isolated_settings")
    def test_no_anthropic_api_key_field(self):
        """Settings class no longer has anthropic_api_key field."""
        settings = Settings(_env_file=None)
        assert not hasattr(settings, "anthropic_api_key")

    @pytest.mark.usefixtures("_isolated_settings")
    def test_no_anthropic_base_url_field(self):
        """Settings class no longer has anthropic_base_url field."""
        settings = Settings(_env_file=None)
        assert not hasattr(settings, "anthropic_base_url")


# ---------------------------------------------------------------------------
# _build_engine tests (Z.ai provider)
# ---------------------------------------------------------------------------


class TestBuildEngineZai:
    """_build_engine with provider=zai uses zai_api_key."""

    @pytest.mark.asyncio
    async def test_build_engine_zai_with_base_url(self, monkeypatch):
        """When zai_base_url is set, AsyncAnthropic receives base_url."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-key")
        monkeypatch.setenv("CODEHIVE_ZAI_BASE_URL", "https://custom.z.ai")

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

        assert captured_kwargs.get("base_url") == "https://custom.z.ai"
        assert captured_kwargs.get("api_key") == "sk-zai-key"

    @pytest.mark.asyncio
    async def test_build_engine_passes_model_from_config(self, monkeypatch):
        """When session config contains model, NativeEngine receives it."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-key")

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
                await _build_engine({"provider": "zai", "model": "glm-4.7"}, engine_type="native")
            except Exception:
                pass

        assert captured_engine_kwargs.get("model") == "glm-4.7"


# ---------------------------------------------------------------------------
# CLI provider resolution tests
# ---------------------------------------------------------------------------


class TestCLIProviderResolution:
    """--provider flag resolves correct api_key, base_url, and model."""

    def test_provider_zai_resolves(self, monkeypatch):
        """--provider zai uses Z.ai base_url and reads ZAI_API_KEY."""
        monkeypatch.setenv("ZAI_API_KEY", "sk-zai-123")
        args = argparse.Namespace(provider="zai", model="")
        api_key, base_url, model = _resolve_provider(args)
        assert api_key == "sk-zai-123"
        assert base_url == "https://api.z.ai/api/anthropic"
        assert model == "glm-4.7"  # default for zai

    def test_provider_zai_with_model(self, monkeypatch):
        """--provider zai --model glm-5 uses Z.ai base_url with glm-5."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-zai-456")
        args = argparse.Namespace(provider="zai", model="glm-5")
        api_key, base_url, model = _resolve_provider(args)
        assert api_key == "sk-zai-456"
        assert base_url == "https://api.z.ai/api/anthropic"
        assert model == "glm-5"

    def test_provider_default_returns_empty_key(self, monkeypatch):
        """When no provider is specified, returns empty key (Claude CLI used)."""
        args = argparse.Namespace(provider="", model="")
        api_key, base_url, model = _resolve_provider(args)
        assert api_key == ""
        assert base_url == ""

    def test_model_without_provider_passes_through(self, monkeypatch):
        """--model without --provider overrides model only."""
        args = argparse.Namespace(provider="", model="claude-opus-4-20250515")
        api_key, base_url, model = _resolve_provider(args)
        assert api_key == ""
        assert model == "claude-opus-4-20250515"

    def test_zai_key_from_codehive_env(self, monkeypatch):
        """CODEHIVE_ZAI_API_KEY takes precedence."""
        monkeypatch.setenv("CODEHIVE_ZAI_API_KEY", "sk-codehive-zai")
        monkeypatch.setenv("ZAI_API_KEY", "sk-plain-zai")
        args = argparse.Namespace(provider="zai", model="")
        api_key, base_url, model = _resolve_provider(args)
        assert api_key == "sk-codehive-zai"


# ---------------------------------------------------------------------------
# CLI sessions create --model tests
# ---------------------------------------------------------------------------


class TestSessionsCreateModel:
    """sessions create --model passes model in config."""

    def test_sessions_create_with_model(self, monkeypatch):
        proj_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "mysession", "id": sess_id}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "create", proj_id, "--name", "mysession", "--model", "glm-4.7"],
                monkeypatch,
            )

        assert code == 0
        body = mock_client.post.call_args[1]["json"]
        assert body["config"] == {"model": "glm-4.7"}

    def test_sessions_create_without_model_no_config(self, monkeypatch):
        proj_id = str(uuid.uuid4())
        sess_id = str(uuid.uuid4())
        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {"name": "mysession", "id": sess_id}

        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("codehive.cli._make_client", return_value=mock_client):
            output, code = _run_cli(
                ["sessions", "create", proj_id, "--name", "mysession"],
                monkeypatch,
            )

        assert code == 0
        body = mock_client.post.call_args[1]["json"]
        assert "config" not in body


# ---------------------------------------------------------------------------
# providers list tests
# ---------------------------------------------------------------------------


class TestProvidersListCommand:
    """codehive providers list outputs a table with provider info."""

    def test_providers_list_output(self, monkeypatch):
        output, code = _run_cli(["providers", "list"], monkeypatch)
        assert code == 0
        assert "claude" in output
        assert "zai" in output
        assert "Provider" in output
        assert "Type" in output

    def test_providers_list_shows_availability(self, monkeypatch):
        """Available column shows yes/no based on CLI presence and keys."""
        monkeypatch.delenv("CODEHIVE_ZAI_API_KEY", raising=False)
        monkeypatch.delenv("ZAI_API_KEY", raising=False)

        output, code = _run_cli(["providers", "list"], monkeypatch)
        assert code == 0
        # Z.ai should show "no" since no key is set
        zai_line = [line for line in output.strip().split("\n") if line.strip().startswith("zai")]
        assert len(zai_line) >= 1
        assert "no" in zai_line[0]

    def test_providers_list_zai_key_set(self, monkeypatch):
        """When ZAI key is set, shows yes."""
        monkeypatch.setenv("ZAI_API_KEY", "sk-zai-test")
        output, code = _run_cli(["providers", "list"], monkeypatch)
        assert code == 0
        zai_line = [line for line in output.strip().split("\n") if line.strip().startswith("zai")]
        assert len(zai_line) >= 1
        assert "yes" in zai_line[0]

    def test_providers_list_shows_default_model(self, monkeypatch):
        output, code = _run_cli(["providers", "list"], monkeypatch)
        assert code == 0
        assert "claude-sonnet-4-20250514" in output
        assert "glm-4.7" in output

    def test_providers_list_shows_all_four(self, monkeypatch):
        """Provider list includes all four providers."""
        output, code = _run_cli(["providers", "list"], monkeypatch)
        assert code == 0
        assert "claude" in output
        assert "codex" in output
        assert "openai" in output
        assert "zai" in output
