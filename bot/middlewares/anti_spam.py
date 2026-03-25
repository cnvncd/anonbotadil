"""
Anti-spam middleware: limits each user to one post per N seconds.

Uses an in-process TTL cache (good for single-instance bots).
For multi-instance deployments replace with a Redis-backed solution.
"""

from __future__ import annotations

import time
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import Message

from bot.config import settings

logger = logging.getLogger(__name__)

# telegram_id → unix timestamp of last accepted post
_last_post_ts: dict[int, float] = {}


class AntiSpamMiddleware(BaseMiddleware):
    """Rate-limit: 1 post per *spam_interval_seconds* per user."""

    async def __call__(
        self,
        handler: Callable[[Message, dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: dict[str, Any],
    ) -> Any:
        user = event.from_user
        if user is None:
            return await handler(event, data)

        # Skip anti-spam for /start command
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        tid = user.id
        now = time.monotonic()
        last = _last_post_ts.get(tid, 0.0)
        elapsed = now - last

        if elapsed < settings.spam_interval_seconds:
            remaining = int(settings.spam_interval_seconds - elapsed)
            logger.debug("Anti-spam triggered for user %s (wait %ss)", tid, remaining)
            await event.answer(
                f"⏳ Подождите {remaining} сек. перед отправкой следующего поста."
            )
            return  # drop the update

        _last_post_ts[tid] = now
        return await handler(event, data)
