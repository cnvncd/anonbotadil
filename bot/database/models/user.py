"""ORM model: users table."""
from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base import Base

if TYPE_CHECKING:
    from bot.database.models.post import Post


class User(Base):
    """Telegram user who interacts with the bot."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    registered_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    posts: Mapped[list[Post]] = relationship(back_populates="user", lazy="selectin")

    def __repr__(self) -> str:
        return f"<User telegram_id={self.telegram_id} username={self.username!r}>"
