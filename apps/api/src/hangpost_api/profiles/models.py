"""ORM models for profiles and current location."""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, UUID
from sqlalchemy.orm import Mapped, mapped_column

from hangpost_api.core.db import Base

# sentence-transformers all-MiniLM-L6-v2 produces 384-dim embeddings.
EMBEDDING_DIM = 384


class Profile(Base):
    """Public-facing profile; the matching engine reads these fields."""

    __tablename__ = "profiles"
    __table_args__ = (CheckConstraint("age BETWEEN 13 AND 120", name="profiles_age_check"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    handle: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    age: Mapped[int | None] = mapped_column(SmallInteger)
    hometown: Mapped[str | None] = mapped_column(Text)
    college: Mapped[str | None] = mapped_column(Text)
    interests: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    liked_topics: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}"
    )
    # Output of hangpost_matching.profile_to_text(); regenerated on edit.
    bio_synthesized: Mapped[str | None] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    embedding_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    onboarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class UserLocation(Base):
    """Most recent reported location; upstream of the radius pre-filter."""

    __tablename__ = "user_locations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    # geography(POINT, 4326): geodesic from day one, no flat-earth math.
    geom: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    accuracy_m: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
