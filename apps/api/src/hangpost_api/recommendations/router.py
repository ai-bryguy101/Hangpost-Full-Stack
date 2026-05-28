"""``GET /recommendations`` — the headline endpoint of Phase 1.

Pipeline (CLAUDE.md §2, §5):

1. Resolve the source profile + the source's last reported location.
2. ``ST_DWithin`` pre-filter on ``user_locations``. Distance is a
   *hard* pre-filter, never a ranking feature.
3. Load candidate profiles in one query.
4. Load mutual-friend ids for source + every candidate so the engine's
   social-boost lane sees a real signal.
5. Hand structured ``UserProfile`` objects + the precomputed embedding
   map to ``hangpost_matching.rank_candidates_with_cold_start``.
6. Log one ``recommendation_impressions`` row per returned candidate
   with the full ``MatchBreakdown`` for the ML loop.

No Clerk auth here yet — Phase 1.4 will replace the ``source_user_id``
query param with the JWT subject (CLAUDE.md §6 / STATUS.md).
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import asdict
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hangpost_api.auth.models import User
from hangpost_api.core.config import get_settings
from hangpost_api.core.db import get_session
from hangpost_api.core.enums import FriendshipState
from hangpost_api.matching.engine import is_available as matching_available
from hangpost_api.matching.engine import rank as matching_rank
from hangpost_api.profiles.models import Profile, UserLocation
from hangpost_api.recommendations.models import RecommendationImpression
from hangpost_api.social.models import Friendship

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

DEFAULT_RADIUS_M = 5_000
MAX_RADIUS_M = 50_000
DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def _to_engine_profile(
    row: Profile,
    mutual_friend_ids: set[str],
) -> Any:
    """Build a ``hangpost_matching.UserProfile`` from a Profile row.

    Imported lazily so the module is import-safe even when the engine
    isn't installed (CI fast path).
    """
    from hangpost_matching import UserProfile

    return UserProfile(
        user_id=str(row.user_id),
        interests=set(row.interests or []),
        liked_topics=set(row.liked_topics or []),
        hometown=row.hometown,
        college=row.college,
        age=row.age,
        mutual_friend_ids=mutual_friend_ids,
    )


async def _accepted_friend_ids(
    session: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[str, set[str]]:
    """Return ``{user_id: {friend_id, ...}}`` for accepted edges only.

    Friendships are stored as a single directed row but the relationship
    they represent is symmetric — so a friend of A is anyone on the
    other end of an ACCEPTED edge that touches A, regardless of which
    side initiated it.
    """
    if not user_ids:
        return {}
    stmt = select(Friendship.requester_id, Friendship.addressee_id).where(
        and_(
            Friendship.state == FriendshipState.ACCEPTED,
            or_(
                Friendship.requester_id.in_(user_ids),
                Friendship.addressee_id.in_(user_ids),
            ),
        )
    )
    rows = (await session.execute(stmt)).all()
    out: dict[str, set[str]] = {str(uid): set() for uid in user_ids}
    targets = {str(uid) for uid in user_ids}
    for requester_id, addressee_id in rows:
        r, a = str(requester_id), str(addressee_id)
        if r in targets:
            out[r].add(a)
        if a in targets:
            out[a].add(r)
    return out


@router.get("", summary="Ranked friend candidates near the source user")
async def get_recommendations(
    source_user_id: Annotated[uuid.UUID, Query(description="UUID of the viewer.")],
    session: Annotated[AsyncSession, Depends(get_session)],
    radius_m: Annotated[
        int,
        Query(
            ge=1,
            le=MAX_RADIUS_M,
            description="Hard pre-filter radius in meters. Never enters the score.",
        ),
    ] = DEFAULT_RADIUS_M,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> dict[str, Any]:
    """Return ranked candidates with explainable score breakdowns.

    Response shape::

        {
          "source_user_id": "...",
          "radius_m": 5000,
          "model_version": "rules-v1",
          "results": [
            {
              "user_id": "...",
              "display_name": "...",
              "handle": "...",
              "rank_position": 1,
              "score": 0.81,
              "breakdown": {... MatchBreakdown ...}
            },
            ...
          ]
        }
    """
    if not matching_available():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Matching engine is not installed in this image.",
        )

    source_profile = (
        await session.execute(select(Profile).where(Profile.user_id == source_user_id))
    ).scalar_one_or_none()
    if source_profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Source profile not found.")

    source_location = (
        await session.execute(
            select(UserLocation).where(UserLocation.user_id == source_user_id)
        )
    ).scalar_one_or_none()
    if source_location is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Source has no reported location; cannot apply radius pre-filter.",
        )

    # Step 2: hard radius pre-filter. ST_DWithin on geography uses meters
    # directly; this is the only place distance touches the pipeline.
    candidate_ids_stmt = (
        select(UserLocation.user_id)
        .join(User, User.id == UserLocation.user_id)
        .where(
            UserLocation.user_id != source_user_id,
            User.deleted_at.is_(None),
            func.ST_DWithin(UserLocation.geom, source_location.geom, radius_m),
        )
    )
    candidate_ids: list[uuid.UUID] = list(
        (await session.execute(candidate_ids_stmt)).scalars().all()
    )
    if not candidate_ids:
        return {
            "source_user_id": str(source_user_id),
            "radius_m": radius_m,
            "model_version": get_settings().model_version,
            "results": [],
        }

    candidate_rows: Sequence[Profile] = (
        await session.execute(select(Profile).where(Profile.user_id.in_(candidate_ids)))
    ).scalars().all()

    # Step 4: mutual-friend lookup for source + all candidates in one query.
    friends = await _accepted_friend_ids(session, [source_user_id, *candidate_ids])
    source_mutuals = friends.get(str(source_user_id), set())

    source_engine_profile = _to_engine_profile(source_profile, source_mutuals)
    candidate_engine_profiles = [
        _to_engine_profile(row, friends.get(str(row.user_id), set()))
        for row in candidate_rows
    ]

    # Step 5: precomputed embeddings (skip rows without one — the engine
    # treats a missing embedding as a 0.0 contribution, not an error).
    embeddings: dict[str, list[float]] = {}
    if source_profile.embedding is not None:
        embeddings[str(source_profile.user_id)] = list(source_profile.embedding)
    for row in candidate_rows:
        if row.embedding is not None:
            embeddings[str(row.user_id)] = list(row.embedding)

    ranked = matching_rank(
        source_engine_profile,
        candidate_engine_profiles,
        profile_embeddings=embeddings or None,
    )
    ranked = ranked[:limit]

    # Index the loaded ORM rows by uuid so we can attach display fields
    # to each ranked engine profile without re-querying.
    rows_by_id = {str(row.user_id): row for row in candidate_rows}
    model_version = get_settings().model_version

    results: list[dict[str, Any]] = []
    impression_values: list[dict[str, Any]] = []
    for position, (engine_profile, breakdown) in enumerate(ranked, start=1):
        row = rows_by_id[engine_profile.user_id]
        breakdown_dict = asdict(breakdown)
        results.append(
            {
                "user_id": str(row.user_id),
                "display_name": row.display_name,
                "handle": row.handle,
                "rank_position": position,
                "score": breakdown.total_score,
                "breakdown": breakdown_dict,
            }
        )
        impression_values.append(
            {
                "source_user_id": source_user_id,
                "candidate_id": row.user_id,
                "rank_position": position,
                "score": breakdown.total_score,
                "model_version": model_version,
                "breakdown_json": breakdown_dict,
            }
        )

    # Step 6: log impressions. This is the seam the ML loop closes against
    # in Phase 7 (CLAUDE.md §5); without it we lose the ground truth that
    # `LearnedRanker.fit()` will eventually consume.
    if impression_values:
        await session.execute(insert(RecommendationImpression), impression_values)
        await session.commit()

    return {
        "source_user_id": str(source_user_id),
        "radius_m": radius_m,
        "model_version": model_version,
        "results": results,
    }
