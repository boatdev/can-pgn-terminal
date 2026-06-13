"""Tests for FastAPI endpoints."""
# pylint: disable=import-error

from app.main import app  # noqa: I001
from fastapi.testclient import TestClient  # noqa: I001

client = TestClient(app)


def test_health_endpoint():
    """Health endpoint should return status ok with live mode."""
    resp = client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["mode"] == "live"


def test_devices_endpoint_returns_list():
    """Devices endpoint should return a list with total and mode."""
    resp = client.get("/api/devices")
    assert resp.status_code == 200
    data = resp.json()
    assert "devices" in data
    assert "total" in data
    assert "mode" in data
    assert data["mode"] == "live"


def test_raw_messages_endpoint():
    """Raw-messages endpoint should return a message list."""
    resp = client.get("/api/raw-messages")
    assert resp.status_code == 200
    data = resp.json()
    assert "messages" in data
    assert "total" in data


def test_values_endpoint():
    """Values endpoint should return a list."""
    resp = client.get("/api/values")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_history_endpoint_missing_params():
    """History endpoint without required params should return 422."""
    resp = client.get("/api/history")
    assert resp.status_code == 422


def test_history_endpoint_with_params():
    """History endpoint with valid params should return a list."""
    resp = client.get("/api/history", params={
        "source_id": 1,
        "pgn": 130306,
        "field_key": "Wind_Speed",
        "window": 60,
    })
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
