import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app

client = TestClient(app)

TEST_API_KEY = "test-backend-api-key-not-a-secret"


def _reload_backend_with_db(monkeypatch, tmp_path, name="test_service_requests.db"):
    db_path = tmp_path / name
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BACKEND_API_KEY", TEST_API_KEY)

    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    return backend_main, database_module


def _authed_client(backend_main):
    test_client = TestClient(backend_main.app)
    test_client.headers["X-API-Key"] = TEST_API_KEY
    return test_client


def test_create_service_request_nominal(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    database_module.init_db()
    with _authed_client(backend_main) as test_client:
        # Créer le prestataire d'abord
        res_p = test_client.post(
            "/api/bot/providers",
            json={
                "telegram_id": 1001,
                "full_name": "Jean Prestataire",
                "phone_number": "+243810000001",
                "services": ["service_plomberie"],
                "communes": ["Gombe"],
                "language": "fr",
            },
        )
        assert res_p.status_code == 200

        # Créer la proposition de service
        response = test_client.post(
            "/api/bot/service-requests",
            json={
                "provider_telegram_id": 1001,
                "service_name": "Soudure industrielle",
                "description": "Spécialiste soudure à l'arc et réparation de portails.",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service_request"]["id"] > 0
        assert data["service_request"]["provider_telegram_id"] == 1001
        assert data["service_request"]["service_name"] == "Soudure industrielle"
        assert data["service_request"]["status"] == "pending"


def test_create_service_request_provider_not_found(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    database_module.init_db()
    with _authed_client(backend_main) as test_client:
        response = test_client.post(
            "/api/bot/service-requests",
            json={
                "provider_telegram_id": 999999,
                "service_name": "Soudure",
                "description": "Description valide mais sans prestataire existant.",
            },
        )
        assert response.status_code == 404


def test_get_pending_service_requests(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    database_module.init_db()
    with _authed_client(backend_main) as test_client:
        # Créer deux prestataires
        for tid, name in [(2001, "Alice"), (2002, "Bob")]:
            test_client.post(
                "/api/bot/providers",
                json={
                    "telegram_id": tid,
                    "full_name": name,
                    "services": ["service_electricite"],
                    "communes": ["Kalamu"],
                },
            )

        test_client.post(
            "/api/bot/service-requests",
            json={
                "provider_telegram_id": 2001,
                "service_name": "Domotique",
                "description": "Installation d'équipements connectés.",
            },
        )
        test_client.post(
            "/api/bot/service-requests",
            json={
                "provider_telegram_id": 2002,
                "service_name": "Menuiserie aluminium",
                "description": "Portes et fenêtres sur mesure.",
            },
        )

        response = test_client.get("/api/bot/service-requests/pending")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert len(data["service_requests"]) == 2
        assert data["service_requests"][0]["provider_name"] == "Alice"
        assert data["service_requests"][1]["provider_name"] == "Bob"


def test_update_service_request_status_flow(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    database_module.init_db()
    with _authed_client(backend_main) as test_client:
        test_client.post(
            "/api/bot/providers",
            json={
                "telegram_id": 3001,
                "full_name": "Charlie",
                "services": ["service_climatisation"],
                "communes": ["Bandalungwa"],
            },
        )

        req_res = test_client.post(
            "/api/bot/service-requests",
            json={
                "provider_telegram_id": 3001,
                "service_name": "Frigoriste",
                "description": "Réparation chambres froides.",
            },
        )
        req_id = req_res.json()["service_request"]["id"]

        # Consulter par ID
        get_res = test_client.get(f"/api/bot/service-requests/{req_id}")
        assert get_res.status_code == 200
        assert get_res.json()["service_request"]["provider_name"] == "Charlie"

        # Accepter
        patch_res = test_client.patch(
            f"/api/bot/service-requests/{req_id}/status",
            json={"status": "accepted", "admin_note": "Service validé pour Kinshasa"},
        )
        assert patch_res.status_code == 200
        assert patch_res.json()["service_request"]["status"] == "accepted"
        assert patch_res.json()["service_request"]["admin_note"] == "Service validé pour Kinshasa"

        # Ne doit plus apparaître dans les pending
        pending_res = test_client.get("/api/bot/service-requests/pending")
        assert len(pending_res.json()["service_requests"]) == 0

        invalid_res = test_client.patch(
            f"/api/bot/service-requests/{req_id}/status",
            json={"status": "unknown"},
        )
        assert invalid_res.status_code == 400

        second_review_res = test_client.patch(
            f"/api/bot/service-requests/{req_id}/status",
            json={"status": "rejected"},
        )
        assert second_review_res.status_code == 400


def test_profile_includes_service_requests(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    database_module.init_db()
    with _authed_client(backend_main) as test_client:
        test_client.post(
            "/api/bot/providers",
            json={
                "telegram_id": 4001,
                "full_name": "David",
                "services": ["service_peinture"],
                "communes": ["Limete"],
            },
        )

        test_client.post(
            "/api/bot/service-requests",
            json={
                "provider_telegram_id": 4001,
                "service_name": "Peinture époxy",
                "description": "Revêtement sols industriels et résine.",
            },
        )

        profile_res = test_client.get("/api/profile/4001")
        assert profile_res.status_code == 200
        profile_data = profile_res.json()
        assert len(profile_data["service_requests"]) == 1
        assert profile_data["service_requests"][0]["service_name"] == "Peinture époxy"
        assert profile_data["service_requests"][0]["status"] == "pending"
