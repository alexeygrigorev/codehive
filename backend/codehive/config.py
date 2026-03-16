"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Codehive application settings.

    All settings can be overridden via environment variables
    prefixed with ``CODEHIVE_``.
    """

    host: str = "127.0.0.1"
    port: int = 7433
    debug: bool = False
    app_name: str = "codehive"
    version: str = ""

    database_url: str = "postgresql+asyncpg://codehive:codehive@localhost:5432/codehive"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    anthropic_base_url: str = ""

    github_default_token: str = ""

    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    telegram_notify_events: list[str] = [
        "approval.required",
        "session.completed",
        "session.failed",
        "subagent.report_ready",
        "question.created",
    ]

    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    vapid_private_key: str = ""
    vapid_public_key: str = ""
    vapid_mailto: str = "mailto:admin@codehive.dev"
    push_notify_events: list[str] = [
        "approval.required",
        "session.completed",
        "session.failed",
        "session.waiting",
        "question.created",
    ]

    firebase_credentials_json: str = ""

    model_config = {
        "env_prefix": "CODEHIVE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }
