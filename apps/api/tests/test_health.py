"""Smoke tests for the app shell — no database required."""

from fastapi.testclient import TestClient

from hangpost_api.main import app

client = TestClient(app)


def test_health_ok() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_sets_request_id_header() -> None:
    resp = client.get("/health")
    assert resp.headers.get("X-Request-ID")


def test_cors_allows_configured_origin() -> None:
    resp = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
