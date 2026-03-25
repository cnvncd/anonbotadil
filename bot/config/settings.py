"""
Application configuration via environment variables.
"""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configurable parameters of the bot."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    bot_token: str
    admin_group_id: int          # Telegram chat_id of the moderation group
    channel_id: int              # Telegram chat_id / @username of the channel

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str            # asyncpg DSN: postgresql+asyncpg://...

    # ── Anti-spam ─────────────────────────────────────────────────────────────
    spam_interval_seconds: int = 60   # min seconds between two posts per user

    # ── Scheduler ─────────────────────────────────────────────────────────────
    scheduler_check_interval: int = 30  # seconds between scheduled-post checks

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = "logs/bot.log"


settings = Settings()  # type: ignore[call-arg]
