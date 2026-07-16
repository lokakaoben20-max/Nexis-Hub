import importlib
import json
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


def test_backend_state_persists_to_disk(tmp_path, monkeypatch):
    state_file = tmp_path / "backend_state.json"
    monkeypatch.setenv("BACKEND_STATE_FILE", str(state_file))

    backend_main = importlib.reload(importlib.import_module("backend.app.main"))

    with TestClient(backend_main.app) as test_client:
        response = test_client.post(
            "/api/bot/users",
            json={
                "telegram_id": 777,
                "first_name": "Alice",
                "phone_number": "+243800000777",
                "language": "fr",
            },
        )
        assert response.status_code == 200

    assert state_file.exists()
    payload = json.loads(state_file.read_text(encoding="utf-8"))
    assert payload["users"]["777"]["phone_number"] == "+243800000777"
