"""
CRUD operations for the users table.
"""
from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import User

logger = logging.getLogger(__name__)


class UserService:
    """Repository-style service for User entities."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_or_create(self, telegram_id: int, username: str | None) -> User:
        """Return existing user or create a new one atomically."""
        stmt = select(User).where(User.telegram_id == telegram_id)
        result = await self._session.execute(stmt)
        user = result.scalar_one_or_none()

        if user is None:
            user = User(telegram_id=telegram_id, username=username)
            self._session.add(user)
            await self._session.flush()
            logger.info("New user registered: telegram_id=%s username=%s", telegram_id, username)
        else:
            # Keep username in sync
            if user.username != username:
                user.username = username

        return user
