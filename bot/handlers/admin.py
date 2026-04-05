"""
Handlers for admin moderation actions:
  approve / reject / archive / schedule
"""

from __future__ import annotations

import datetime
import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import settings
from bot.keyboards import schedule_keyboard
from bot.services.post_service import PostService
from bot.services.publisher import publish_post

logger = logging.getLogger(__name__)
router = Router(name="admin")

# ── FSM for manual schedule input ─────────────────────────────────────────────


class ScheduleState(StatesGroup):
    waiting_for_datetime = State()
    post_id = State()


# ── Helpers ───────────────────────────────────────────────────────────────────


def _is_admin_group(query: CallbackQuery) -> bool:
    return (
        query.message is not None and query.message.chat.id == settings.admin_group_id
    )


async def _notify_user_rejected(bot: Bot, post_id: int, session: AsyncSession) -> None:
    """Send rejection notice to the post author."""
    from bot.database.models import Post
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    stmt = select(Post).where(Post.id == post_id).options(selectinload(Post.user))
    result = await session.execute(stmt)
    post = result.scalar_one_or_none()

    if post and post.user:
        try:
            await bot.send_message(
                post.user.telegram_id,
                "❌ Ваш пост не прошел модерацию.",
            )
        except Exception:
            logger.warning("Could not notify user about rejection, post_id=%s", post_id)


# ── Approve ───────────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(query: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not _is_admin_group(query):
        return

    post_id = int(query.data.split(":")[1])
    svc = PostService(session)
    post = await svc.approve(post_id)

    if post is None:
        await query.answer("Пост не найден.", show_alert=True)
        return

    success = await publish_post(bot, post)
    if success:
        await svc.mark_published(post_id)
        await session.commit()
        await query.answer("✅ Пост опубликован.")
        if query.message:
            await query.message.edit_text(f"✅ Пост #{post_id} — опубликован.")
    else:
        await query.answer("⚠️ Ошибка публикации.", show_alert=True)

    logger.info("Admin %s approved post %s", query.from_user.id, post_id)


# ── Reject ────────────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(query: CallbackQuery, session: AsyncSession, bot: Bot) -> None:
    if not _is_admin_group(query):
        return

    post_id = int(query.data.split(":")[1])
    svc = PostService(session)
    await svc.reject(post_id)
    await _notify_user_rejected(bot, post_id, session)
    await session.commit()

    await query.answer("❌ Пост отклонён.")
    if query.message:
        await query.message.edit_text(f"❌ Пост #{post_id} — отклонён.")
    logger.info("Admin %s rejected post %s", query.from_user.id, post_id)


# ── Archive ───────────────────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("archive:"))
async def cb_archive(query: CallbackQuery, session: AsyncSession) -> None:
    if not _is_admin_group(query):
        return

    post_id = int(query.data.split(":")[1])
    svc = PostService(session)
    await svc.archive(post_id)
    await session.commit()

    await query.answer("📦 Пост архивирован.")
    if query.message:
        await query.message.edit_text(f"📦 Пост #{post_id} — в архиве.")
    logger.info("Admin %s archived post %s", query.from_user.id, post_id)


# ── Schedule: pick time ───────────────────────────────────────────────────────


@router.callback_query(F.data.startswith("schedule:"))
async def cb_schedule_menu(query: CallbackQuery) -> None:
    if not _is_admin_group(query):
        return

    post_id = int(query.data.split(":")[1])
    await query.answer()
    if query.message:
        await query.message.edit_reply_markup(reply_markup=schedule_keyboard(post_id))


@router.callback_query(F.data.startswith("sched_time:"))
async def cb_sched_time(
    query: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    if not _is_admin_group(query):
        return

    _, post_id_str, delta_str = query.data.split(":")
    post_id = int(post_id_str)

    if delta_str == "manual":
        await state.set_state(ScheduleState.waiting_for_datetime)
        await state.update_data(post_id=post_id)
        await query.answer()
        if query.message:
            await query.message.reply(
                "✏️ Введите дату и время публикации в формате:\n<code>DD.MM.YYYY HH:MM</code>",
                parse_mode="HTML",
            )
        return

    delta_map = {
        "30m": datetime.timedelta(minutes=30),
        "1h": datetime.timedelta(hours=1),
        "3h": datetime.timedelta(hours=3),
        "1d": datetime.timedelta(days=1),
    }
    delta = delta_map.get(delta_str)
    if delta is None:
        await query.answer("Неизвестный интервал.", show_alert=True)
        return

    publish_at = datetime.datetime.now(tz=datetime.timezone.utc) + delta

    svc = PostService(session)
    await svc.schedule(post_id, publish_at)
    await session.commit()

    await query.answer(
        f"⏳ Запланировано на {publish_at.strftime('%d.%m.%Y %H:%M')} UTC"
    )
    if query.message:
        await query.message.edit_text(
            f"⏳ Пост #{post_id} — запланирован на {publish_at.strftime('%d.%m.%Y %H:%M')} UTC"
        )
    logger.info(
        "Admin %s scheduled post %s at %s", query.from_user.id, post_id, publish_at
    )


# ── Schedule: manual datetime input ──────────────────────────────────────────


@router.message(ScheduleState.waiting_for_datetime)
async def handle_manual_datetime(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
) -> None:
    # Only process messages from admin group
    if message.chat.id != settings.admin_group_id:
        return

    data = await state.get_data()
    post_id: int = data["post_id"]

    try:
        naive_dt = datetime.datetime.strptime(message.text or "", "%d.%m.%Y %H:%M")
        # Convert from UTC+5 to UTC
        utc_plus_5 = datetime.timezone(datetime.timedelta(hours=5))
        local_dt = naive_dt.replace(tzinfo=utc_plus_5)
        publish_at = local_dt.astimezone(datetime.timezone.utc)
    except ValueError:
        await message.reply(
            "❗ Неверный формат. Попробуйте: <code>DD.MM.YYYY HH:MM</code>",
            parse_mode="HTML",
        )
        return

    svc = PostService(session)
    await svc.schedule(post_id, publish_at)
    await session.commit()
    await state.clear()

    # Display in UTC+5 for user
    utc_plus_5 = datetime.timezone(datetime.timedelta(hours=5))
    local_time = publish_at.astimezone(utc_plus_5)
    await message.reply(
        f"⏳ Пост #{post_id} запланирован на {local_time.strftime('%d.%m.%Y %H:%M')} (UTC+5)."
    )
    logger.info(
        "Admin %s manually scheduled post %s at %s",
        message.from_user.id if message.from_user else "unknown",
        post_id,
        publish_at,
    )


# ── View archived posts ──────────────────────────────────────────────────────


@router.message(F.text == "/archive")
async def cmd_view_archive(message: Message, session: AsyncSession) -> None:
    """Show list of archived posts."""
    if message.chat.id != settings.admin_group_id:
        return

    from bot.database.models import Post, PostStatus
    from sqlalchemy import select

    stmt = (
        select(Post)
        .where(Post.status == PostStatus.ARCHIVED)
        .order_by(Post.created_at.desc())
        .limit(20)
    )
    result = await session.execute(stmt)
    archived_posts = result.scalars().all()

    if not archived_posts:
        await message.reply("📦 Архив пуст.")
        return

    response = "📦 <b>Архивные посты (последние 20):</b>\n\n"
    for post in archived_posts:
        created = post.created_at.astimezone(
            datetime.timezone(datetime.timedelta(hours=5))
        )
        response += f"#{post.id} — {post.content_type.value} — {created.strftime('%d.%m.%Y %H:%M')}\n"
        if post.text:
            preview = post.text[:50] + "..." if len(post.text) > 50 else post.text
            response += f"   {preview}\n"
        response += "\n"

    await message.reply(response, parse_mode="HTML")
