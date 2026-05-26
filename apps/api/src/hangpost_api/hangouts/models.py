"""ORM models for hangouts and their RSVPs."""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from hangpost_api.core.db import Base
from hangpost_api.core.enums import HangoutStatus, RsvpStatus

_hangout_status = Enum(
    HangoutStatus,
    name="hangout_status",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)
_rsvp_status = Enum(
    RsvpStatus,
    name="rsvp_status",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)


class Hangout(Base):
    """Time/place metadata for a post of type ``hangout``."""

    __tablename__ = "hangouts"

    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        primary_key=True,
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    venue: Mapped[str | None] = mapped_column(Text)
    max_rsvps: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[HangoutStatus] = mapped_column(
        _hangout_status, nullable=False, server_default=HangoutStatus.OPEN.value
    )


class HangoutRsvp(Base):
    """A user's RSVP to a hangout."""

    __tablename__ = "hangout_rsvps"

    hangout_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hangouts.post_id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[RsvpStatus] = mapped_column(_rsvp_status, nullable=False)
    rsvped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
