"""
Application entry-point.

Run with:
    python -m bot.main
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.database.engine import engine
from bot.database.models import Base
from bot.handlers import get_root_router
from bot.middlewares import AntiSpamMiddleware, DbSessionMiddleware
from bot.services.scheduler import scheduled_publisher_loop
from bot.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


async def on_startup(bot: Bot) -> None:
    """Create DB tables and log startup info."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    me = await bot.get_me()
    logger.info("Bot started: @%s (id=%s)", me.username, me.id)


async def on_shutdown(bot: Bot) -> None:
    """Cleanup resources."""
    await engine.dispose()
    logger.info("Bot shutdown complete.")


async def main() -> None:
    setup_logging()
    logger.info("Starting anonymous post bot…")

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    storage = MemoryStorage()  # swap for RedisStorage for multi-instance
    dp = Dispatcher(storage=storage)

    # ── Middlewares ────────────────────────────────────────────────────────────
    dp.message.middleware(DbSessionMiddleware())
    dp.callback_query.middleware(DbSessionMiddleware())

    # Anti-spam only on regular messages (not callbacks)
    dp.message.middleware(AntiSpamMiddleware())

    # ── Routers ───────────────────────────────────────────────────────────────
    dp.include_router(get_root_router())

    # ── Lifecycle hooks ───────────────────────────────────────────────────────
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    # ── Background tasks ──────────────────────────────────────────────────────
    # asyncio.get_event_loop() is deprecated in 3.10+; use create_task() inside async context
    scheduler_task = asyncio.create_task(scheduled_publisher_loop(bot))

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
