"""ORM models for the recommendation impression/outcome log."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    SmallInteger,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hangpost_api.core.db import Base


class RecommendationImpression(Base):
    """One ranked candidate surfaced to one user, with full provenance."""

    __tablename__ = "recommendation_impressions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    source_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    surfaced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    rank_position: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    model_version: Mapped[str] = mapped_column(Text, nullable=False)
    # The full MatchBreakdown returned by the ranker, stored verbatim.
    breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class RecommendationOutcome(Base):
    """Downstream actions for an impression; the training label source."""

    __tablename__ = "recommendation_outcomes"

    impression_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("recommendation_impressions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    profile_opened: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    friend_request_sent: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    blocked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    hangout_rsvped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
