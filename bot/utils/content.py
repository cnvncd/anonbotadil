"""
Helper utilities for content-type detection and media-group handling.
"""
from __future__ import annotations

from aiogram.types import Message

from bot.database.models import ContentType


def detect_content_type(message: Message) -> ContentType:
    """Infer the *ContentType* of an incoming Telegram message."""
    if message.photo:
        return ContentType.PHOTO
    if message.video:
        return ContentType.VIDEO
    if message.voice:
        return ContentType.VOICE
    if message.document:
        return ContentType.DOCUMENT
    if message.media_group_id:
        return ContentType.MEDIA_GROUP
    if message.text and message.entities:
        for entity in message.entities:
            if entity.type in ("url", "text_link"):
                return ContentType.LINK
    return ContentType.TEXT


def extract_file_id(message: Message) -> str | None:
    """Return the primary file_id from a message, if any."""
    if message.photo:
        return message.photo[-1].file_id   # largest size
    if message.video:
        return message.video.file_id
    if message.voice:
        return message.voice.file_id
    if message.document:
        return message.document.file_id
    return None
