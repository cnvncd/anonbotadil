"""Configure structured logging for the application."""
from __future__ import annotations

import logging
import logging.handlers
import os

from bot.config import settings


def setup_logging() -> None:
    """Set up root logger with console + rotating file handler."""
    os.makedirs("logs", exist_ok=True)

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    handlers: list[logging.Handler] = [logging.StreamHandler()]

    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,   # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handlers.append(file_handler)

    logging.basicConfig(
        level=settings.log_level.upper(),
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )

    # Silence noisy third-party loggers
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
