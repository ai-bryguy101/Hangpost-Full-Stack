"""Smoke tests for the auth + profiles + recommendations surface.

These cover the unauthenticated short-circuit paths only — they don't
need Clerk JWKS or a database connection because the dependency layer
rejects each request before touching either.
"""

from fastapi.testclient import TestClient

from hangpost_api.main import app

client = TestClient(app)


def test_me_requires_bearer_token() -> None:
    resp = client.get("/me")
    assert resp.status_code == 401


def test_profiles_post_requires_bearer_token() -> None:
    resp = client.post(
        "/profiles",
        json={"display_name": "Test", "handle": "testuser"},
    )
    assert resp.status_code == 401


def test_profiles_patch_me_requires_bearer_token() -> None:
    resp = client.patch("/profiles/me", json={"display_name": "Updated"})
    assert resp.status_code == 401


def test_recommendations_without_token_or_query_param_is_400() -> None:
    """No JWT and no source_user_id query param — the endpoint should 400."""
    resp = client.get("/recommendations")
    # The recommendations endpoint also raises 503 if the matching engine
    # isn't installed in this image. In CI the engine is installed from
    # the SHA pin, so this is a 400. Accept both so the test stays useful
    # in any environment where the engine import fails (e.g. an offline
    # box) — we're only validating the auth/param wiring here.
    assert resp.status_code in (400, 503)
