"""ORM model for the core identity table."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hangpost_api.core.db import Base


class User(Base):
    """A person who has authenticated, regardless of profile completeness."""

    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("auth_provider", "auth_sub"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    auth_provider: Mapped[str] = mapped_column(String, nullable=False)
    auth_sub: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    phone: Mapped[str | None] = mapped_column(String, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Soft delete keeps rows for GDPR audit while removing the user from views.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
