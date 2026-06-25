from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDMixin


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    display_name: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default=text("'user'"),
    )

    is_verified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )