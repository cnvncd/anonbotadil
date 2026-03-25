"""
Handlers for regular users:
  /start command
  Post submission (text, photo, video, voice, document)
"""

from __future__ import annotations

import logging

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


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Welcome message."""
    await message.answer(
        "👋 Отправьте сообщение, и оно может быть опубликовано анонимно.\n\n"
        "Поддерживается: текст, фото, видео, голосовые, документы, ссылки."
    )


async def _forward_to_admins(bot: Bot, post_id: int, message: Message) -> int | None:
    """
    Forward the original message to the admin group for moderation.

    Returns the admin message_id or None on failure.
    """
    try:
        header = await bot.send_message(
            settings.admin_group_id,
            f"📨 <b>Новый пост #{post_id}</b>",
            parse_mode="HTML",
        )
        # Forward original content so admins see it as-is
        fwd = await message.forward(settings.admin_group_id)
        # Attach moderation buttons to a separate control message
        ctrl = await bot.send_message(
            settings.admin_group_id,
            f"⬆️ Пост #{post_id} — выберите действие:",
            reply_markup=moderation_keyboard(post_id),
        )
        _ = header, fwd  # held for reference; we track the control message
        return ctrl.message_id
    except Exception:
        logger.exception("Failed to forward post %s to admins", post_id)
        return None


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
    admin_msg_id = await _forward_to_admins(bot, post.id, message)
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
