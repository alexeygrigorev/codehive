"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Codehive application settings.

    All settings can be overridden via environment variables
    prefixed with ``CODEHIVE_``.
    """

    host: str = "127.0.0.1"
    port: int = 8000
    debug: bool = False
    app_name: str = "codehive"
    version: str = ""

    database_url: str = "postgresql+asyncpg://codehive:codehive@localhost:5432/codehive"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    anthropic_base_url: str = ""

    github_default_token: str = ""

    model_config = {
        "env_prefix": "CODEHIVE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
