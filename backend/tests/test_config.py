"""Tests for codehive.config.Settings."""

from pathlib import Path

import pytest

from codehive.config import Settings


@pytest.fixture()
def _isolated_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Clear all CODEHIVE_* env vars and point Settings away from real .env files."""
    import os

    for key in list(os.environ):
        if key.startswith("CODEHIVE_"):
            monkeypatch.delenv(key)
    # Also clear provider-specific vars
    for key in ("ANTHROPIC_API_KEY", "ANTHROPIC_BASE_URL", "ZAI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)


class TestSettingsDefaults:
    @pytest.mark.usefixtures("_isolated_settings")
    def test_default_host(self):
        settings = Settings(_env_file=None)
        assert settings.host == "127.0.0.1"

    @pytest.mark.usefixtures("_isolated_settings")
    def test_default_port(self):
        settings = Settings(_env_file=None)
        assert settings.port == 7433

    @pytest.mark.usefixtures("_isolated_settings")
    def test_default_debug(self):
        settings = Settings(_env_file=None)
        assert settings.debug is False


class TestSettingsEnvOverride:
    def test_override_host(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_HOST", "0.0.0.0")
        settings = Settings()
        assert settings.host == "0.0.0.0"

    def test_override_port(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_PORT", "9000")
        settings = Settings()
        assert settings.port == 9000

    def test_override_debug(self, monkeypatch):
        monkeypatch.setenv("CODEHIVE_DEBUG", "true")
        settings = Settings()
        assert settings.debug is True


class TestDatabaseSettings:
    """Tests for database and Redis URL configuration (issue #02)."""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_database_url_default(self):
        """Verify database_url returns the expected default SQLite connection string."""
        settings = Settings(_env_file=None)
        assert settings.database_url == "sqlite+aiosqlite:///data/codehive.db"

    @pytest.mark.usefixtures("_isolated_settings")
    def test_redis_url_default(self):
        """Verify redis_url defaults to empty string (no Redis = LocalEventBus)."""
        settings = Settings(_env_file=None)
        assert settings.redis_url == ""

    def test_database_url_override(self, monkeypatch):
        """Verify database_url can be overridden via environment variable."""
        custom_url = "postgresql+asyncpg://user:pass@db.example.com:5432/mydb"
        monkeypatch.setenv("CODEHIVE_DATABASE_URL", custom_url)
        settings = Settings()
        assert settings.database_url == custom_url

    def test_redis_url_override(self, monkeypatch):
        """Verify redis_url can be overridden via environment variable."""
        custom_url = "redis://redis.example.com:6379/1"
        monkeypatch.setenv("CODEHIVE_REDIS_URL", custom_url)
        settings = Settings()
        assert settings.redis_url == custom_url


class TestConfigCleanup:
    """Tests for removed anthropic config fields (issue #110)."""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_no_anthropic_api_key_field(self):
        """Settings class no longer has anthropic_api_key."""
        settings = Settings(_env_file=None)
        assert not hasattr(settings, "anthropic_api_key")

    @pytest.mark.usefixtures("_isolated_settings")
    def test_no_anthropic_base_url_field(self):
        """Settings class no longer has anthropic_base_url."""
        settings = Settings(_env_file=None)
        assert not hasattr(settings, "anthropic_base_url")

    @pytest.mark.usefixtures("_isolated_settings")
    def test_settings_instantiates_without_anthropic_key(self):
        """Settings() succeeds without CODEHIVE_ANTHROPIC_API_KEY env var."""
        settings = Settings(_env_file=None)
        assert settings.host == "127.0.0.1"  # basic sanity

    @pytest.mark.usefixtures("_isolated_settings")
    def test_openai_api_key_still_exists(self):
        """Settings still has openai_api_key field."""
        settings = Settings(_env_file=None)
        assert hasattr(settings, "openai_api_key")
        assert settings.openai_api_key == ""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_zai_api_key_still_exists(self):
        """Settings still has zai_api_key field."""
        settings = Settings(_env_file=None)
        assert hasattr(settings, "zai_api_key")
        assert settings.zai_api_key == ""

    @pytest.mark.usefixtures("_isolated_settings")
    def test_zai_base_url_still_exists(self):
        """Settings still has zai_base_url field."""
        settings = Settings(_env_file=None)
        assert hasattr(settings, "zai_base_url")


class TestEnvFileLoading:
    """Tests for .env file loading."""

    def test_settings_loads_from_env_file(self, tmp_path, monkeypatch):
        """Settings picks up values from a .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("CODEHIVE_HOST=10.0.0.1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        settings = Settings(_env_file=env_file)
        assert settings.host == "10.0.0.1"

    @pytest.mark.usefixtures("_isolated_settings")
    def test_env_file_loads_zai_key(self, tmp_path, monkeypatch):
        """Settings picks up zai_api_key from a .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("CODEHIVE_ZAI_API_KEY=sk-zai-123\n", encoding="utf-8")
        settings = Settings(_env_file=env_file)
        assert settings.zai_api_key == "sk-zai-123"

    def test_env_var_overrides_env_file(self, tmp_path, monkeypatch):
        """Environment variables take precedence over .env file values."""
        env_file = tmp_path / ".env"
        env_file.write_text("CODEHIVE_PORT=3000\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CODEHIVE_PORT", "4000")
        settings = Settings(_env_file=env_file)
        assert settings.port == 4000

    @pytest.mark.usefixtures("_isolated_settings")
    def test_missing_env_file_uses_defaults(self, tmp_path, monkeypatch):
        """When no .env file exists, defaults are used without error."""
        settings = Settings(_env_file=tmp_path / "nonexistent.env")
        assert settings.host == "127.0.0.1"


class TestEnvExampleCompleteness:
    """Verify .env.example contains entries for important Settings fields."""

    def test_env_example_contains_key_settings_fields(self):
        """Key fields should have a corresponding CODEHIVE_ entry in .env.example."""
        env_example_path = Path(__file__).resolve().parents[2] / ".env.example"
        content = env_example_path.read_text(encoding="utf-8")

        expected_fields = [
            "CODEHIVE_HOST",
            "CODEHIVE_PORT",
            "CODEHIVE_DEBUG",
            "CODEHIVE_DATABASE_URL",
            "CODEHIVE_REDIS_URL",
            "CODEHIVE_OPENAI_API_KEY",
            "CODEHIVE_ZAI_API_KEY",
            "CODEHIVE_ZAI_BASE_URL",
        ]
        for field in expected_fields:
            assert field in content, f"{field} missing from .env.example"

    def test_env_example_no_anthropic_key(self):
        """CODEHIVE_ANTHROPIC_API_KEY should NOT appear in .env.example."""
        env_example_path = Path(__file__).resolve().parents[2] / ".env.example"
        content = env_example_path.read_text(encoding="utf-8")
        assert "CODEHIVE_ANTHROPIC_API_KEY" not in content
        assert "CODEHIVE_ANTHROPIC_BASE_URL" not in content
