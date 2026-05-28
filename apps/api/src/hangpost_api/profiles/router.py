"""Profile create + edit endpoints.

``POST /profiles`` creates the current user's profile (one per user).
``PATCH /profiles/me`` partially updates it. Both endpoints synthesize
``bio_synthesized`` and recompute the pgvector ``embedding`` whenever
any engine-relevant field is supplied, so the ranker always sees a
fresh vector for that user without a separate backfill step.

Handle uniqueness is enforced by the CITEXT unique constraint on the
column; the duplicate is caught and reported as a 409 to keep the
error visible to the client instead of leaking as a 500.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from hangpost_api.auth.dependencies import get_current_user
from hangpost_api.auth.models import User
from hangpost_api.core.db import get_session
from hangpost_api.profiles.embedder import embed_profile_fields
from hangpost_api.profiles.models import Profile
from hangpost_api.profiles.schemas import ProfileCreate, ProfileRead, ProfileUpdate

router = APIRouter(prefix="/profiles", tags=["profiles"])

# Fields that, when changed, invalidate the cached embedding. Mirrors the
# inputs to hangpost_matching.profile_to_text().
_EMBED_FIELDS = frozenset({"age", "hometown", "college", "interests", "liked_topics"})


async def _load_profile(session: AsyncSession, user_id: str) -> Profile | None:
    return (
        await session.execute(select(Profile).where(Profile.user_id == user_id))
    ).scalar_one_or_none()


@router.post(
    "",
    response_model=ProfileRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create the current user's profile",
)
async def create_profile(
    payload: ProfileCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Profile:
    """Create the one ``profiles`` row for the authenticated user.

    Returns 409 if a profile already exists for this user or the handle
    is taken; both collisions surface from the database's unique
    constraints.
    """
    existing = await _load_profile(session, str(current_user.id))
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Profile already exists; use PATCH /profiles/me to edit it.",
        )

    bio, embedding = await embed_profile_fields(
        str(current_user.id),
        interests=payload.interests,
        liked_topics=payload.liked_topics,
        hometown=payload.hometown,
        college=payload.college,
        age=payload.age,
    )
    now = datetime.now(UTC) if embedding is not None else None

    profile = Profile(
        user_id=current_user.id,
        display_name=payload.display_name,
        handle=payload.handle,
        avatar_url=payload.avatar_url,
        age=payload.age,
        hometown=payload.hometown,
        college=payload.college,
        interests=payload.interests,
        liked_topics=payload.liked_topics,
        bio_synthesized=bio or None,
        embedding=embedding,
        embedding_at=now,
        onboarded_at=datetime.now(UTC),
    )
    session.add(profile)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Handle is already taken.",
        ) from exc
    await session.refresh(profile)
    return profile


@router.get("/me", response_model=ProfileRead, summary="Read the current user's profile")
async def read_my_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Profile:
    profile = await _load_profile(session, str(current_user.id))
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No profile yet; POST /profiles to create one.",
        )
    return profile


@router.patch("/me", response_model=ProfileRead, summary="Update the current user's profile")
async def update_my_profile(
    payload: ProfileUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Profile:
    profile = await _load_profile(session, str(current_user.id))
    if profile is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="No profile yet; POST /profiles to create one.",
        )

    # exclude_unset means we only see fields the client actually sent —
    # critical for partial updates (a missing field must NOT be set to None).
    changes = payload.model_dump(exclude_unset=True)
    if not changes:
        return profile

    for field, value in changes.items():
        setattr(profile, field, value)
    profile.updated_at = datetime.now(UTC)

    if _EMBED_FIELDS.intersection(changes):
        bio, embedding = await embed_profile_fields(
            str(current_user.id),
            interests=profile.interests,
            liked_topics=profile.liked_topics,
            hometown=profile.hometown,
            college=profile.college,
            age=profile.age,
        )
        profile.bio_synthesized = bio or None
        profile.embedding = embedding
        profile.embedding_at = datetime.now(UTC) if embedding is not None else None

    await session.commit()
    await session.refresh(profile)
    return profile
