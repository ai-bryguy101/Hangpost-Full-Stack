"""FastAPI dependencies that turn a Clerk JWT into a ``User`` row.

Clerk hands the browser a signed JWT; the API verifies it against the
project's published JWKS (set via ``CLERK_JWKS_URL`` — see
:mod:`hangpost_api.core.config`) and treats the token's ``sub`` claim
as a stable third-party identifier. The first time we see a sub, we
upsert a ``users`` row keyed by ``(auth_provider='clerk', auth_sub)``;
subsequent requests re-use the same row.

Two dependencies are exposed:

- :func:`get_current_user` — required auth; returns the ``User`` ORM
  row or raises 401.
- :func:`get_current_user_optional` — best-effort auth; returns
  ``None`` when no token is supplied. Used by endpoints that want a
  short-term "logged-in or query-param fallback" path while the
  frontend is still being wired (see ``recommendations/router.py``).

The JWKS client is process-cached; PyJWT handles key rotation on its
own once the URL is set.
"""

from __future__ import annotations

from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import PyJWKClient
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from hangpost_api.auth.models import User
from hangpost_api.core.config import get_settings
from hangpost_api.core.db import get_session

CLERK_AUTH_PROVIDER = "clerk"

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    """Return a process-cached PyJWKClient pointed at the configured URL.

    Raises 503 if ``CLERK_JWKS_URL`` isn't set — that's a deployment
    misconfiguration, not a client error.
    """
    global _jwks_client
    if _jwks_client is None:
        jwks_url = get_settings().clerk_jwks_url
        if not jwks_url:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Auth not configured (CLERK_JWKS_URL is unset).",
            )
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def _verify_token(token: str) -> dict[str, Any]:
    """Verify a Clerk JWT and return its decoded claims.

    Audience is intentionally not checked: Clerk JWTs use the issuer
    (Clerk instance domain) as the primary trust anchor, and Clerk's
    own SDK leaves ``aud`` verification off by default. We can tighten
    this up when we move to a production Clerk instance with a known
    audience id.
    """
    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            signing_key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
        ) from exc


def _bearer_token(authorization: str | None) -> str | None:
    """Pull the bearer token from an ``Authorization`` header, if any."""
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def _upsert_clerk_user(
    session: AsyncSession, sub: str, email: str | None
) -> User:
    """Upsert the ``users`` row for a Clerk sub and return the ORM object.

    On conflict we update the email so a user changing their Clerk email
    is reflected on the next request. Email collisions across different
    subs will surface as a 500 — first-write-wins is acceptable while
    the user base is synthetic.
    """
    effective_email = email or f"clerk-{sub}@hangpost.test"
    stmt = (
        pg_insert(User)
        .values(
            auth_provider=CLERK_AUTH_PROVIDER,
            auth_sub=sub,
            email=effective_email,
        )
        .on_conflict_do_update(
            index_elements=[User.auth_provider, User.auth_sub],
            set_={"email": effective_email},
        )
        .returning(User)
    )
    user = (await session.execute(stmt)).scalar_one()
    await session.commit()
    return user


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Required-auth dependency: 401s when the token is missing/invalid."""
    token = _bearer_token(authorization)
    if not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    claims = _verify_token(token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Token has no sub claim.",
        )
    return await _upsert_clerk_user(session, sub=sub, email=claims.get("email"))


async def get_current_user_optional(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
) -> User | None:
    """Optional-auth dependency: returns ``None`` when no token is sent.

    A *malformed* token still raises 401 — silently ignoring bad tokens
    would mask client bugs. Only the no-header case falls through.
    """
    token = _bearer_token(authorization)
    if not token:
        return None
    claims = _verify_token(token)
    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            detail="Token has no sub claim.",
        )
    return await _upsert_clerk_user(session, sub=sub, email=claims.get("email"))
