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
