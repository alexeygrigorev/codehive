"""Application configuration via environment variables."""

from typing import Any

from pydantic_settings import BaseSettings
from pydantic_settings.sources import EnvSettingsSource


class _CorsEnvSource(EnvSettingsSource):
    """Env source that parses ``cors_origins`` as a comma-separated string."""

    def prepare_field_value(
        self,
        field_name: str,
        field: Any,
        value: Any,
        value_is_complex: bool,
    ) -> Any:
        if field_name == "cors_origins" and isinstance(value, str):
            return [o.strip() for o in value.split(",") if o.strip()]
        return super().prepare_field_value(field_name, field, value, value_is_complex)


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

    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql+asyncpg://codehive:codehive@localhost:5432/codehive"
    redis_url: str = "redis://localhost:6379/0"

    anthropic_api_key: str = ""
    anthropic_base_url: str = ""

    zai_api_key: str = ""
    zai_base_url: str = "https://api.z.ai/api/anthropic"
    default_model: str = "claude-sonnet-4-20250514"

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

    auth_enabled: bool = False

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

    backup_dir: str = "./backups"
    backup_retention: int = 7

    error_window_minutes: int = 15
    error_spike_threshold: float = 3.0
    error_spike_min_count: int = 5
    error_spike_cooldown_seconds: int = 300
    error_monitor_interval_seconds: int = 60

    firebase_credentials_json: str = ""

    log_level: str = "INFO"
    log_file: str = ""
    log_json: bool = True

    admin_username: str = "admin"
    admin_password: str = ""

    model_config = {
        "env_prefix": "CODEHIVE_",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any = None,
        env_settings: Any = None,
        dotenv_settings: Any = None,
        file_secret_settings: Any = None,
        **kwargs: Any,
    ) -> tuple:
        """Use custom env source that handles comma-separated cors_origins."""
        return (
            init_settings,
            _CorsEnvSource(settings_cls),
            dotenv_settings,
            file_secret_settings,
        )
