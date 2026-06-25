"""The messages table. One row per turn (user or assistant)."""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, ForeignKey, Index, Integer, String, Text, func, text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import UUIDMixin


class Message(UUIDMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (Index("ix_messages_chat_created", "chat_id", "created_at"),)

    chat_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chats.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # "user" | "assistant"
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Filled in only for assistant messages:
    provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_complete: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), nullable=False
    )