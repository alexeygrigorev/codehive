"""Tests for codehive.config.Settings."""

from codehive.config import Settings


class TestSettingsDefaults:
    def test_default_host(self):
        settings = Settings()
        assert settings.host == "127.0.0.1"

    def test_default_port(self):
        settings = Settings()
        assert settings.port == 8000

    def test_default_debug(self):
        settings = Settings()
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

    def test_database_url_default(self):
        """Verify database_url returns the expected default Postgres connection string."""
        settings = Settings()
        assert settings.database_url == (
            "postgresql+asyncpg://codehive:codehive@localhost:5432/codehive"
        )

    def test_redis_url_default(self):
        """Verify redis_url returns the expected default Redis connection string."""
        settings = Settings()
        assert settings.redis_url == "redis://localhost:6379/0"

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
