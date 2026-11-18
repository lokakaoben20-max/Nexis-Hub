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
        ("/api/bot/payments", {"quote_id": 10, "payment_status": "paid_escrow", "mission_id": 111}),
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


def test_payment_and_mission_lifecycle_reject_invalid_transitions(monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", TEST_KEY)
    headers = {"X-Nexis-Internal-Key": TEST_KEY}
    mission_id = 33321

    created = client.post(
        "/api/bot/missions",
        json={"telegram_id": 101, "mission_id": mission_id,
              "service": "service_plomberie", "commune": "Gombe"},
        headers=headers,
    )
    assert created.status_code == 200
    assert created.json()["mission"]["payment_status"] == "unpaid"

    # No mission can start or complete before an internal payment confirmation.
    assert client.post(
        "/api/bot/missions/status",
        json={"mission_id": mission_id, "status": "in_progress"},
        headers=headers,
    ).status_code == 409
    assert client.post(
        "/api/bot/payments",
        json={"mission_id": mission_id, "quote_id": 55, "payment_status": "released"},
        headers=headers,
    ).status_code == 422

    payment = {"mission_id": mission_id, "quote_id": 55, "payment_status": "paid_escrow"}
    assert client.post("/api/bot/payments", json=payment, headers=headers).status_code == 200
    assert client.post("/api/bot/payments", json=payment, headers=headers).status_code == 200
    assert client.post(
        "/api/bot/payments",
        json={**payment, "quote_id": 56},
        headers=headers,
    ).status_code == 409

    assert client.post(
        "/api/bot/missions/status",
        json={"mission_id": mission_id, "status": "completed", "payment_status": "released"},
        headers=headers,
    ).status_code == 409

    for status in ("in_progress", "awaiting_confirmation"):
        assert client.post(
            "/api/bot/missions/status",
            json={"mission_id": mission_id, "status": status},
            headers=headers,
        ).status_code == 200

    assert client.post(
        "/api/bot/missions/status",
        json={"mission_id": mission_id, "status": "completed"},
        headers=headers,
    ).status_code == 409
    release = {"mission_id": mission_id, "status": "completed", "payment_status": "released"}
    assert client.post(
        "/api/bot/missions/status", json=release, headers=headers,
    ).status_code == 200
    assert client.post(
        "/api/bot/missions/status", json=release, headers=headers,
    ).status_code == 200

    # A retried mission sync cannot reset a completed mission to pending.
    retried = client.post(
        "/api/bot/missions",
        json={"telegram_id": 101, "mission_id": mission_id,
              "service": "service_plomberie", "commune": "Gombe"},
        headers=headers,
    )
    assert retried.status_code == 200
    assert retried.json()["mission"]["status"] == "completed"
