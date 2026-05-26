"""ORM models for the friend graph and import provenance."""

import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from hangpost_api.core.db import Base
from hangpost_api.core.enums import FriendshipState

_friendship_state = Enum(
    FriendshipState,
    name="friendship_state",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)


class Friendship(Base):
    """A directed friendship edge with a lifecycle state."""

    __tablename__ = "friendships"
    __table_args__ = (
        CheckConstraint("requester_id <> addressee_id", name="friendships_no_self"),
    )

    requester_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    addressee_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    state: Mapped[FriendshipState] = mapped_column(_friendship_state, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class FriendshipImport(Base):
    """Provenance for a batch of imported friend edges (contacts, etc.)."""

    __tablename__ = "friendship_imports"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    source: Mapped[str] = mapped_column(Text, nullable=False)
    imported_count: Mapped[int] = mapped_column(Integer, nullable=False)
    # Proof that the user consented to the import flow (GDPR provenance).
    consent_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
