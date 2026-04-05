"""
Publishes approved / scheduled posts to the Telegram channel.
"""

from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError

from bot.config import settings
from bot.database.models import Post, ContentType

logger = logging.getLogger(__name__)


async def publish_post(bot: Bot, post: Post) -> bool:
    """
    Send *post* to the configured channel.

    Returns True on success, False on any Telegram error.
    """
    channel = settings.channel_id
    caption = post.text if post.text else None

    try:
        match post.content_type:
            case ContentType.TEXT | ContentType.LINK:
                text_body = post.text if post.text else ""
                await bot.send_message(channel, text_body, parse_mode="HTML")

            case ContentType.PHOTO:
                await bot.send_photo(
                    channel,
                    photo=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )

            case ContentType.VIDEO:
                await bot.send_video(
                    channel,
                    video=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )

            case ContentType.VOICE:
                await bot.send_voice(
                    channel,
                    voice=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )

            case ContentType.DOCUMENT:
                await bot.send_document(
                    channel,
                    document=post.media_file_id,
                    caption=caption,
                    parse_mode="HTML",
                )

            case ContentType.MEDIA_GROUP:
                # media_file_id stores pipe-separated "type:file_id" pairs
                await _send_media_group(bot, channel, post)

            case _:
                logger.warning("Unknown content type for post id=%s", post.id)
                return False

        logger.info("Published post id=%s to channel=%s", post.id, channel)
        return True

    except TelegramAPIError as exc:
        logger.error("Failed to publish post id=%s: %s", post.id, exc)
        return False


async def _send_media_group(bot: Bot, channel: int, post: Post) -> None:
    """Handle comma-separated media group items stored as 'type:file_id'."""
    from aiogram.types import (
        InputMediaPhoto,
        InputMediaVideo,
        InputMediaDocument,
    )

    media_items = []
    pairs = (post.media_file_id or "").split(",")

    for idx, pair in enumerate(pairs):
        if ":" not in pair:
            logger.warning(
                "Invalid media_group format for post id=%s: %s", post.id, pair
            )
            continue
        media_type, file_id = pair.split(":", 1)
        cap = post.text if (post.text and idx == 0) else None

        match media_type:
            case "photo":
                media_items.append(
                    InputMediaPhoto(media=file_id, caption=cap, parse_mode="HTML")
                )
            case "video":
                media_items.append(
                    InputMediaVideo(media=file_id, caption=cap, parse_mode="HTML")
                )
            case "document":
                media_items.append(
                    InputMediaDocument(media=file_id, caption=cap, parse_mode="HTML")
                )

    if media_items:
        await bot.send_media_group(channel, media=media_items)
