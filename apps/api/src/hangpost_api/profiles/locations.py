"""``POST /user-locations`` — set the current user's GPS location.

The location feeds the ``ST_DWithin`` radius pre-filter that
``GET /recommendations`` runs before ranking (CLAUDE.md §2: distance is
a *hard* pre-filter, never a ranking signal). One row per user, upserted
on every fix. The geometry is written as EWKT so PostGIS stores a
``geography(POINT, 4326)`` exactly the way the seed corpus does (see
``seed.py``) — real users and synthetic users then look identical to the
pre-filter.

Lives in the ``profiles`` package because that package owns the
``user_locations`` table; it gets its own ``/user-locations`` router so
the public path stays flat rather than nesting under ``/profiles``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from hangpost_api.auth.dependencies import get_current_user
from hangpost_api.auth.models import User
from hangpost_api.core.db import get_session
from hangpost_api.profiles.models import UserLocation
from hangpost_api.profiles.schemas import LocationCreate, LocationRead

router = APIRouter(prefix="/user-locations", tags=["locations"])


@router.post(
    "",
    response_model=LocationRead,
    status_code=status.HTTP_200_OK,
    summary="Set the current user's location",
)
async def upsert_my_location(
    payload: LocationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> LocationRead:
    """Create or replace the authenticated user's single location row.

    Idempotent: re-posting overwrites the previous fix and bumps
    ``updated_at`` (hence 200, not 201). PostGIS ``POINT`` takes
    ``(longitude latitude)`` order, the reverse of how humans say it.
    """
    stmt = insert(UserLocation).values(
        user_id=current_user.id,
        geom=f"SRID=4326;POINT({payload.longitude} {payload.latitude})",
        accuracy_m=payload.accuracy_m,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[UserLocation.user_id],
        set_={
            "geom": stmt.excluded.geom,
            "accuracy_m": stmt.excluded.accuracy_m,
            "updated_at": func.now(),
        },
    ).returning(UserLocation.updated_at)
    updated_at = (await session.execute(stmt)).scalar_one()
    await session.commit()

    return LocationRead(
        latitude=payload.latitude,
        longitude=payload.longitude,
        accuracy_m=payload.accuracy_m,
        updated_at=updated_at,
    )
