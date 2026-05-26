"""ORM models for posterboard posts and their attached media."""

import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import (
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
from hangpost_api.core.enums import PostType, PostVisibility

_post_type = Enum(
    PostType,
    name="post_type",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)
_post_visibility = Enum(
    PostVisibility,
    name="post_visibility",
    create_type=False,
    values_callable=lambda e: [m.value for m in e],
)


class Post(Base):
    """A single posterboard entry: a hangout opportunity or local info."""

    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    author_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[PostType] = mapped_column(_post_type, nullable=False)
    visibility: Mapped[PostVisibility] = mapped_column(_post_visibility, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    posted_geom: Mapped[str] = mapped_column(
        Geography(geometry_type="POINT", srid=4326), nullable=False
    )
    radius_m: Mapped[int] = mapped_column(Integer, nullable=False, server_default="5000")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PostMedia(Base):
    """An image attached to a post, stored in Cloudflare R2."""

    __tablename__ = "post_media"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    post_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("posts.id", ondelete="CASCADE"),
        nullable=False,
    )
    r2_key: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
