"""
Handlers for regular users:
  /start command
  Post submission (text, photo, video, voice, document, media_group)
"""

from __future__ import annotations

import logging
import asyncio
from collections import defaultdict

from aiogram import Bot, F, Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.keyboards import moderation_keyboard
from bot.services.post_service import PostService
from bot.services.user_service import UserService
from bot.utils.content import detect_content_type, extract_file_id

logger = logging.getLogger(__name__)
router = Router(name="user")

# Store media_group messages temporarily: media_group_id -> list of messages
_media_groups: dict[str, list[Message]] = defaultdict(list)
_media_group_tasks: dict[str, asyncio.Task] = {}


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Welcome message."""
    await message.answer(
        "👋 Отправьте сообщение, и оно может быть опубликовано анонимно.\n\n"
        "Поддерживается: текст, фото, видео, голосовые, документы, ссылки."
    )


async def _forward_to_admins(
    bot: Bot, post_id: int, messages: list[Message]
) -> int | None:
    """
    Send the message content to the admin group for moderation (without forwarding).
    Supports both single messages and media groups.

    Returns the admin message_id or None on failure.
    """
    try:
        header = await bot.send_message(
            settings.admin_group_id,
            f"📨 <b>Новый пост #{post_id}</b>",
            parse_mode="HTML",
        )

        # Handle media group (multiple messages)
        if len(messages) > 1:
            from aiogram.types import (
                InputMediaPhoto,
                InputMediaVideo,
                InputMediaDocument,
            )

            media_items = []
            for idx, msg in enumerate(messages):
                caption = msg.caption if idx == 0 else None

                if msg.photo:
                    media_items.append(
                        InputMediaPhoto(media=msg.photo[-1].file_id, caption=caption)
                    )
                elif msg.video:
                    media_items.append(
                        InputMediaVideo(media=msg.video.file_id, caption=caption)
                    )
                elif msg.document:
                    media_items.append(
                        InputMediaDocument(media=msg.document.file_id, caption=caption)
                    )

            if media_items:
                await bot.send_media_group(settings.admin_group_id, media=media_items)
        else:
            # Single message
            message = messages[0]
            if message.photo:
                await bot.send_photo(
                    settings.admin_group_id,
                    photo=message.photo[-1].file_id,
                    caption=message.caption,
                )
            elif message.video:
                await bot.send_video(
                    settings.admin_group_id,
                    video=message.video.file_id,
                    caption=message.caption,
                )
            elif message.voice:
                await bot.send_voice(
                    settings.admin_group_id,
                    voice=message.voice.file_id,
                    caption=message.caption,
                )
            elif message.document:
                await bot.send_document(
                    settings.admin_group_id,
                    document=message.document.file_id,
                    caption=message.caption,
                )
            else:
                await bot.send_message(
                    settings.admin_group_id,
                    message.text or "",
                )

        # Attach moderation buttons to a separate control message
        ctrl = await bot.send_message(
            settings.admin_group_id,
            f"⬆️ Пост #{post_id} — выберите действие:",
            reply_markup=moderation_keyboard(post_id),
        )
        return ctrl.message_id
    except Exception:
        logger.exception("Failed to forward post %s to admins", post_id)
        return None


async def _process_media_group(
    media_group_id: str,
    messages: list[Message],
    session: AsyncSession,
    bot: Bot,
) -> None:
    """Process collected media group messages as a single post."""
    if not messages:
        return

    first_msg = messages[0]
    tg_user = first_msg.from_user
    if tg_user is None:
        return

    # Upsert user
    user_svc = UserService(session)
    user = await user_svc.get_or_create(tg_user.id, tg_user.username)

    # Build media_file_id as comma-separated "type:file_id" pairs
    media_parts = []
    for msg in messages:
        if msg.photo:
            media_parts.append(f"photo:{msg.photo[-1].file_id}")
        elif msg.video:
            media_parts.append(f"video:{msg.video.file_id}")
        elif msg.document:
            media_parts.append(f"document:{msg.document.file_id}")

    media_file_id = ",".join(media_parts)
    text = first_msg.caption  # Only first message can have caption

    # Persist post
    from bot.database.models import ContentType

    post_svc = PostService(session)
    post = await post_svc.create(
        user_id=user.id,
        content_type=ContentType.MEDIA_GROUP,
        text=text,
        media_file_id=media_file_id,
    )
    await session.commit()

    # Forward to admins
    admin_msg_id = await _forward_to_admins(bot, post.id, messages)
    if admin_msg_id:
        await post_svc.set_admin_message_id(post.id, admin_msg_id)
        await session.commit()

    await first_msg.answer(
        "✅ Ваш пост отправлен на модерацию. После проверки он будет опубликован анонимно."
    )
    logger.info(
        "Media group post submitted: id=%s user_telegram_id=%s items=%d",
        post.id,
        tg_user.id,
        len(messages),
    )


@router.message(F.content_type.in_({"text", "photo", "video", "voice", "document"}))
async def handle_post(message: Message, session: AsyncSession, bot: Bot) -> None:
    """Accept any supported content, save it and send to admin group."""
    tg_user = message.from_user
    if tg_user is None:
        return

    # Ignore messages from admin group and channel
    if (
        message.chat.id == settings.admin_group_id
        or message.chat.id == settings.channel_id
    ):
        return

    # Only accept messages from private chats
    if message.chat.type != "private":
        return

    # Handle media group (album)
    if message.media_group_id:
        media_group_id = message.media_group_id
        _media_groups[media_group_id].append(message)

        # Cancel existing task if any
        if media_group_id in _media_group_tasks:
            _media_group_tasks[media_group_id].cancel()

        # Wait 1 second for all messages in the group to arrive
        async def delayed_process():
            await asyncio.sleep(1)
            messages = _media_groups.pop(media_group_id, [])
            _media_group_tasks.pop(media_group_id, None)
            if messages:
                await _process_media_group(media_group_id, messages, session, bot)

        task = asyncio.create_task(delayed_process())
        _media_group_tasks[media_group_id] = task
        return

    # Upsert user
    user_svc = UserService(session)
    user = await user_svc.get_or_create(tg_user.id, tg_user.username)

    # Detect content
    content_type = detect_content_type(message)
    file_id = extract_file_id(message)
    text = message.text or message.caption

    # Persist post
    post_svc = PostService(session)
    post = await post_svc.create(
        user_id=user.id,
        content_type=content_type,
        text=text,
        media_file_id=file_id,
    )
    await session.commit()

    # Forward to admins
    admin_msg_id = await _forward_to_admins(bot, post.id, [message])
    if admin_msg_id:
        await post_svc.set_admin_message_id(post.id, admin_msg_id)
        await session.commit()

    await message.answer(
        "✅ Ваш пост отправлен на модерацию. После проверки он будет опубликован анонимно."
    )
    logger.info(
        "Post submitted: id=%s user_telegram_id=%s type=%s",
        post.id,
        tg_user.id,
        content_type,
    )
