"""
Middleware that injects an async DB session into every handler's *data* dict.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.database.engine import AsyncSessionFactory


class DbSessionMiddleware(BaseMiddleware):
    """Provide *session* key in handler data; commit on success, rollback on error."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        async with AsyncSessionFactory() as session:
            data["session"] = session
            try:
                return await handler(event, data)
            except Exception:
                await session.rollback()
                raise
