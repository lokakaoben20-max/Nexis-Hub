import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app


client = TestClient(app)
TEST_KEY = "test-nexis-internal-key"


def test_health_endpoint_is_public(monkeypatch):
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_profile_requires_valid_internal_key(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", TEST_KEY)

    assert client.get("/api/profile/12345").status_code == 401
    assert client.get(
        "/api/profile/12345",
        headers={"X-Nexis-Internal-Key": "bad-key"},
    ).status_code == 401

    response = client.get(
        "/api/profile/12345",
        headers={"X-Nexis-Internal-Key": TEST_KEY},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["telegram_id"] == 12345
    assert "client" in payload
    assert "provider" in payload


def test_backend_refuses_requests_when_key_is_not_configured(monkeypatch):
    monkeypatch.delenv("BACKEND_API_KEY", raising=False)
    response = client.get(
        "/api/profile/12345",
        headers={"X-Nexis-Internal-Key": TEST_KEY},
    )
    assert response.status_code == 503


def test_all_mutation_routes_reject_missing_key(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", TEST_KEY)
    routes = [
        ("/api/bot/users", {"telegram_id": 12345}),
        ("/api/bot/missions", {
            "telegram_id": 12345,
            "mission_id": 111,
            "service": "service_plomberie",
            "commune": "Gombe",
        }),
        ("/api/bot/providers", {
            "telegram_id": 54321,
            "full_name": "Prestataire test",
        }),
        ("/api/bot/missions/status", {"mission_id": 111, "status": "completed"}),
        ("/api/bot/payments", {"quote_id": 10, "payment_status": "paid_escrow"}),
    ]
    for path, payload in routes:
        response = client.post(path, json=payload)
        assert response.status_code == 401, path


def test_authenticated_bot_can_sync_user(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", TEST_KEY)
    response = client.post(
        "/api/bot/users",
        json={"telegram_id": 87654, "first_name": "Alice"},
        headers={"X-Nexis-Internal-Key": TEST_KEY},
    )
    assert response.status_code == 200
    assert response.json()["user"]["telegram_id"] == 87654
