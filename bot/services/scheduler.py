"""
Background asyncio task that polls the DB for scheduled posts and publishes them.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot

from bot.config import settings
from bot.database.engine import AsyncSessionFactory
from bot.services.post_service import PostService
from bot.services.publisher import publish_post

logger = logging.getLogger(__name__)


async def scheduled_publisher_loop(bot: Bot) -> None:
    """
    Infinite loop: every *scheduler_check_interval* seconds check for
    scheduled posts whose time has arrived and publish them.
    """
    logger.info("Scheduled publisher loop started (interval=%ss)", settings.scheduler_check_interval)

    while True:
        await asyncio.sleep(settings.scheduler_check_interval)
        try:
            await _process_due_posts(bot)
        except Exception:
            logger.exception("Unhandled error in scheduled_publisher_loop")


async def _process_due_posts(bot: Bot) -> None:
    async with AsyncSessionFactory() as session:
        svc = PostService(session)
        due_posts = await svc.get_due_scheduled()

        for post in due_posts:
            success = await publish_post(bot, post)
            if success:
                await svc.mark_published(post.id)
            # Commit per post so a single failure doesn't roll back everything
            await session.commit()

        if due_posts:
            logger.info("Processed %d scheduled post(s)", len(due_posts))
