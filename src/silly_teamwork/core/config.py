from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Silly Teamwork API"
    environment: Literal["development", "testing", "production"] = "development"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    secret_key: str = "local-development-only-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = Field(default=30, gt=0)

    database_url: str = (
        "postgresql+asyncpg://silly_teamwork:silly_teamwork@localhost:5432/silly_teamwork"
    )
    db_echo: bool = False

    allowed_origins: list[str] = Field(default_factory=list)
    upload_dir: Path = Path("uploads")
    max_file_size: int = Field(default=20 * 1024 * 1024, gt=0)
    max_avatar_size: int = Field(default=5 * 1024 * 1024, gt=0)
    max_upload_size_mb: int = Field(default=20, gt=0)

    # Kept for rollback compatibility. The independent notification scheduler is
    # the default reminder path; enabling this would run the legacy API scanner.
    deadline_reminders_enabled: bool = False
    deadline_reminder_interval_seconds: int = Field(default=300, gt=0)
    deadline_due_soon_hours: int = Field(default=72, gt=0)

    notification_scheduler_interval_seconds: int = Field(default=60, gt=0)
    notification_scheduler_batch_size: int = Field(default=100, gt=0)
    notification_scheduler_lease_seconds: int = Field(default=300, gt=0)
    notification_scheduler_max_attempts: int = Field(default=5, gt=0)

    # AI assistant (Xiaomi MiMo API, OpenAI-compatible protocol).
    ai_llm_enabled: bool = False
    ai_llm_api_key: SecretStr = SecretStr("")
    ai_llm_base_url: str = ""
    ai_llm_model: str = ""
    ai_llm_timeout_seconds: float = Field(default=30, gt=0)
    ai_llm_max_tokens: int = Field(default=2000, gt=0)

    seed_admin_username: str = "admin"
    seed_admin_password: SecretStr = SecretStr("admin123456")
    seed_admin_nickname: str = "Administrator"
    seed_team_name: str = "Silly Teamwork Development Team"
    seed_invite_code: SecretStr = SecretStr("ST-DEV-2026")


@lru_cache
def get_settings() -> Settings:
    return Settings()
