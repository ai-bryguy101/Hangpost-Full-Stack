"""Pydantic request/response models for the profiles endpoints."""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

# 3-30 chars, letters/digits/underscore. Mirrors the CITEXT handle column;
# loose enough for varied display tastes, strict enough to keep URLs sane.
_HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{3,30}$")


def _dedupe_lower(items: list[str]) -> list[str]:
    """Drop empties, dedupe case-insensitively, preserve first-seen order.

    Set membership in the matching engine is case-sensitive, so this
    keeps stored values stable across writes.
    """
    seen: set[str] = set()
    out: list[str] = []
    for raw in items:
        cleaned = raw.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


class ProfileCreate(BaseModel):
    """Fields a user supplies on first profile creation.

    ``handle`` and ``display_name`` are app-side concerns the matching
    engine never sees; the rest mirror ``hangpost_matching.UserProfile``.
    """

    display_name: str = Field(min_length=1, max_length=50)
    handle: str = Field(min_length=3, max_length=30)
    avatar_url: str | None = Field(default=None, max_length=2048)
    age: int | None = Field(default=None, ge=13, le=120)
    hometown: str | None = Field(default=None, max_length=120)
    college: str | None = Field(default=None, max_length=160)
    interests: list[str] = Field(default_factory=list, max_length=64)
    liked_topics: list[str] = Field(default_factory=list, max_length=64)

    @field_validator("handle")
    @classmethod
    def _handle_pattern(cls, v: str) -> str:
        if not _HANDLE_RE.match(v):
            raise ValueError("handle must be 3-30 chars: letters, digits, underscore")
        return v

    @field_validator("interests", "liked_topics")
    @classmethod
    def _normalise_list(cls, v: list[str]) -> list[str]:
        return _dedupe_lower(v)


class ProfileUpdate(BaseModel):
    """Partial update — every field optional; only supplied fields change.

    ``handle`` is intentionally not updatable here; renaming a handle has
    URL/social-graph implications and gets its own endpoint when needed.
    """

    display_name: str | None = Field(default=None, min_length=1, max_length=50)
    avatar_url: str | None = Field(default=None, max_length=2048)
    age: int | None = Field(default=None, ge=13, le=120)
    hometown: str | None = Field(default=None, max_length=120)
    college: str | None = Field(default=None, max_length=160)
    interests: list[str] | None = Field(default=None, max_length=64)
    liked_topics: list[str] | None = Field(default=None, max_length=64)

    @field_validator("interests", "liked_topics")
    @classmethod
    def _normalise_list(cls, v: list[str] | None) -> list[str] | None:
        return None if v is None else _dedupe_lower(v)


class ProfileRead(BaseModel):
    """Profile shape returned to clients (no embedding vector)."""

    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    display_name: str
    handle: str
    avatar_url: str | None
    age: int | None
    hometown: str | None
    college: str | None
    interests: list[str]
    liked_topics: list[str]
    bio_synthesized: str | None
    embedding_at: datetime | None
    onboarded_at: datetime | None
    updated_at: datetime
