"""Auth-domain HTTP endpoints.

Currently just ``GET /me`` — the canonical "is my Clerk JWT valid and
which user does it map to" probe. Profile create/edit lives on the
profiles router; this stays a thin identity-only surface.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from hangpost_api.auth.dependencies import get_current_user
from hangpost_api.auth.models import User
from hangpost_api.auth.schemas import MeRead

router = APIRouter(tags=["auth"])


@router.get("/me", response_model=MeRead, summary="Current authenticated user")
async def get_me(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    """Return the ``users`` row for the bearer of the current Clerk JWT."""
    return current_user
