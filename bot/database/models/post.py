"""ORM model: posts table."""
from __future__ import annotations

import datetime
import enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.models.base import Base

if TYPE_CHECKING:
    from bot.database.models.user import User


class PostStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SCHEDULED = "scheduled"
    ARCHIVED = "archived"
    PUBLISHED = "published"


class ContentType(str, enum.Enum):
    TEXT = "text"
    PHOTO = "photo"
    VIDEO = "video"
    VOICE = "voice"
    DOCUMENT = "document"
    LINK = "link"
    MEDIA_GROUP = "media_group"


class Post(Base):
    """Submitted anonymous post."""

    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)

    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType, name="content_type_enum"), nullable=False
    )
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Stored as comma-separated file_ids for media groups; single id otherwise
    media_file_id: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    status: Mapped[PostStatus] = mapped_column(
        Enum(PostStatus, name="post_status_enum"),
        default=PostStatus.PENDING,
        nullable=False,
        index=True,
    )

    # Telegram message_id of the moderation message in the admin group
    admin_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    scheduled_time: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="posts")

    def __repr__(self) -> str:
        return f"<Post id={self.id} status={self.status} type={self.content_type}>"
