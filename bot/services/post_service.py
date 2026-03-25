"""
CRUD and business-logic operations for the posts table.
"""
from __future__ import annotations

import datetime
import logging
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import Post, PostStatus

logger = logging.getLogger(__name__)


class PostService:
    """Repository-style service for Post entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ── Create ────────────────────────────────────────────────────────────────

    async def create(
        self,
        user_id: int,
        content_type: str,
        text: str | None = None,
        media_file_id: str | None = None,
    ) -> Post:
        """Persist a new post with *pending* status."""
        post = Post(
            user_id=user_id,
            content_type=content_type,
            text=text,
            media_file_id=media_file_id,
            status=PostStatus.PENDING,
        )
        self._session.add(post)
        await self._session.flush()
        logger.info("Post created: id=%s user_id=%s type=%s", post.id, user_id, content_type)
        return post

    # ── Read ──────────────────────────────────────────────────────────────────

    async def get_by_id(self, post_id: int) -> Post | None:
        return await self._session.get(Post, post_id)

    async def get_last_user_post_time(self, user_id: int) -> datetime.datetime | None:
        """Return the created_at of the most recent post for this user."""
        stmt = (
            select(Post.created_at)
            .where(Post.user_id == user_id)
            .order_by(Post.created_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_due_scheduled(self) -> Sequence[Post]:
        """Return all scheduled posts whose publish time has passed."""
        now = datetime.datetime.now(tz=datetime.timezone.utc)
        stmt = (
            select(Post)
            .where(Post.status == PostStatus.SCHEDULED)
            .where(Post.scheduled_time <= now)
        )
        result = await self._session.execute(stmt)
        return result.scalars().all()

    # ── Update ────────────────────────────────────────────────────────────────

    async def set_admin_message_id(self, post_id: int, message_id: int) -> None:
        await self._session.execute(
            update(Post).where(Post.id == post_id).values(admin_message_id=message_id)
        )

    async def approve(self, post_id: int) -> Post | None:
        post = await self.get_by_id(post_id)
        if post:
            post.status = PostStatus.APPROVED
            logger.info("Post approved: id=%s", post_id)
        return post

    async def reject(self, post_id: int) -> Post | None:
        post = await self.get_by_id(post_id)
        if post:
            post.status = PostStatus.REJECTED
            logger.info("Post rejected: id=%s", post_id)
        return post

    async def archive(self, post_id: int) -> Post | None:
        post = await self.get_by_id(post_id)
        if post:
            post.status = PostStatus.ARCHIVED
            logger.info("Post archived: id=%s", post_id)
        return post

    async def schedule(self, post_id: int, publish_at: datetime.datetime) -> Post | None:
        post = await self.get_by_id(post_id)
        if post:
            post.status = PostStatus.SCHEDULED
            post.scheduled_time = publish_at
            logger.info("Post scheduled: id=%s at=%s", post_id, publish_at.isoformat())
        return post

    async def mark_published(self, post_id: int) -> Post | None:
        post = await self.get_by_id(post_id)
        if post:
            post.status = PostStatus.PUBLISHED
            post.published_at = datetime.datetime.now(tz=datetime.timezone.utc)
            logger.info("Post published: id=%s", post_id)
        return post
