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
# Cleanup interval: remove entries older than 2x spam_interval
_CLEANUP_THRESHOLD = settings.spam_interval_seconds * 2


def _cleanup_old_entries() -> None:
    """Remove entries older than cleanup threshold to prevent memory leak."""
    now = time.monotonic()
    to_remove = [
        tid for tid, ts in _last_post_ts.items() if now - ts > _CLEANUP_THRESHOLD
    ]
    for tid in to_remove:
        del _last_post_ts[tid]
    if to_remove:
        logger.debug("Cleaned up %d old anti-spam entries", len(to_remove))


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

        # Skip anti-spam for commands
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        # Skip anti-spam for non-private chats
        if event.chat.type != "private":
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

        # Periodically cleanup old entries (every ~100 requests)
        if len(_last_post_ts) % 100 == 0:
            _cleanup_old_entries()

        return await handler(event, data)
