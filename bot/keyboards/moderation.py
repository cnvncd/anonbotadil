"""
Keyboard factories for moderation and scheduling.
"""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def moderation_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Four-button moderation panel attached to each post in the admin group."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Одобрить", callback_data=f"confirm_approve:{post_id}"
        ),
        InlineKeyboardButton(
            text="❌ Отклонить", callback_data=f"confirm_reject:{post_id}"
        ),
    )
    builder.row(
        InlineKeyboardButton(text="⏳ Отложить", callback_data=f"schedule:{post_id}"),
        InlineKeyboardButton(
            text="📦 Архив", callback_data=f"confirm_archive:{post_id}"
        ),
    )
    return builder.as_markup()


def confirmation_keyboard(action: str, post_id: int) -> InlineKeyboardMarkup:
    """Confirmation dialog for moderation actions."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✔️ Да", callback_data=f"{action}:{post_id}"),
        InlineKeyboardButton(
            text="✖️ Отмена", callback_data=f"back_to_moderation:{post_id}"
        ),
    )
    return builder.as_markup()


def schedule_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Time-picker for deferred publishing."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="30 минут", callback_data=f"sched_time:{post_id}:30m"
        ),
        InlineKeyboardButton(text="1 час", callback_data=f"sched_time:{post_id}:1h"),
    )
    builder.row(
        InlineKeyboardButton(text="3 часа", callback_data=f"sched_time:{post_id}:3h"),
        InlineKeyboardButton(text="Завтра", callback_data=f"sched_time:{post_id}:1d"),
    )
    builder.row(
        InlineKeyboardButton(
            text="✏️ Указать вручную", callback_data=f"sched_time:{post_id}:manual"
        )
    )
    builder.row(
        InlineKeyboardButton(
            text="◀️ Назад", callback_data=f"back_to_moderation:{post_id}"
        )
    )
    return builder.as_markup()
