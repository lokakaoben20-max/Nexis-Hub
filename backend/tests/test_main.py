import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_profile_endpoint_returns_payload_for_telegram_id():
    response = client.get("/api/profile/12345")
    assert response.status_code == 200
    payload = response.json()
    assert payload["telegram_id"] == 12345
    assert "client" in payload
    assert "provider" in payload
