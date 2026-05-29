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


def test_user_locations_post_requires_bearer_token() -> None:
    resp = client.post(
        "/user-locations",
        json={"latitude": 38.9, "longitude": -77.0, "accuracy_m": 20},
    )
    assert resp.status_code == 401


def test_recommendations_requires_bearer_token() -> None:
    """No JWT — the endpoint is Clerk-auth-only now, so it must 401.

    The source_user_id query-param fallback was retired; the auth
    dependency rejects the request before the matching engine is ever
    touched, so this is a 401 regardless of whether the engine is
    installed in the image.
    """
    resp = client.get("/recommendations")
    assert resp.status_code == 401
