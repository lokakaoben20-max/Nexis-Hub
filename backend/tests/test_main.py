import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app

client = TestClient(app)


def _reload_backend_with_db(monkeypatch, tmp_path, name="test_backend.db"):
    db_path = tmp_path / name
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    return backend_main, database_module


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_profile_endpoint_returns_payload_for_telegram_id(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        response = test_client.get("/api/profile/12345")
        assert response.status_code == 200
        payload = response.json()
        assert payload["telegram_id"] == 12345
        assert "client" in payload
        assert "provider" in payload


def test_backend_state_persists_to_db(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

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
        assert response.json()["user"]["phone_number"] == "+243800000777"

    # A fresh session against the same DB file must still see the row.
    with database_module.SessionLocal() as db:
        from backend.app.models import BotUser

        user = db.get(BotUser, 777)
        assert user is not None
        assert user.phone_number == "+243800000777"


def test_mission_lifecycle_round_trip(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        create_response = test_client.post(
            "/api/bot/missions",
            json={
                "telegram_id": 42,
                "mission_id": 1001,
                "service": "plomberie",
                "commune": "Gombe",
                "currency": "USD",
                "description": "Fuite d'eau",
                "urgent": True,
            },
        )
        assert create_response.status_code == 200
        assert create_response.json()["mission"]["status"] is None

        status_response = test_client.post(
            "/api/bot/missions/status",
            json={"mission_id": 1001, "status": "confirmed"},
        )
        assert status_response.status_code == 200
        assert status_response.json()["mission"]["status"] == "confirmed"

        payment_response = test_client.post(
            "/api/bot/payments",
            json={"quote_id": 1, "mission_id": 1001, "payment_status": "paid_escrow"},
        )
        assert payment_response.status_code == 200
        assert payment_response.json()["mission"]["payment_status"] == "paid_escrow"

        profile_response = test_client.get("/api/profile/42")
        missions = profile_response.json()["client_missions"]
        assert len(missions) == 1
        assert missions[0]["payment_status"] == "paid_escrow"


def _register_provider(test_client, telegram_id, services, communes, **overrides):
    payload = {
        "telegram_id": telegram_id,
        "full_name": overrides.pop("full_name", f"Provider {telegram_id}"),
        "phone_number": "+243800000000",
        "services": services,
        "communes": communes,
    }
    response = test_client.post("/api/bot/providers", json=payload)
    assert response.status_code == 200
    return response.json()["provider"]


def test_provider_module_is_computed_from_services(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        plumbing = _register_provider(test_client, 1, ["service_plomberie"], ["Gombe"])
        assert plumbing["module"] == "B"

        painting = _register_provider(test_client, 2, ["service_peinture"], ["Gombe"])
        assert painting["module"] == "A"


def test_provider_registration_resets_status_on_update(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])

        with database_module.SessionLocal() as db:
            from backend.app.models import BotProvider

            provider = db.get(BotProvider, 1)
            provider.status = "paused"
            db.commit()

        updated = _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])
        assert updated["status"] == "available"


def test_matching_filters_by_service_commune_and_ranks_by_score(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])  # matches, default score
        _register_provider(test_client, 2, ["service_peinture"], ["Kintambo"])  # wrong commune
        _register_provider(test_client, 3, ["service_plomberie"], ["Gombe"])  # wrong service
        _register_provider(test_client, 4, ["service_peinture"], ["Gombe"])  # low score
        _register_provider(test_client, 5, ["service_peinture"], ["Gombe"])  # high score

        with database_module.SessionLocal() as db:
            from backend.app.models import BotProvider

            low = db.get(BotProvider, 4)
            low.badge = "pending"
            low.rating = 1.0
            high = db.get(BotProvider, 5)
            high.badge = "partner"
            high.rating = 5.0
            high.success_rate = 100
            db.commit()

        response = test_client.get("/api/bot/providers/matching", params={"service": "service_peinture", "commune": "Gombe"})
        assert response.status_code == 200
        matches = response.json()["providers"]
        assert [p["telegram_id"] for p in matches] == [5, 4, 1]


def _setup_mission_with_quote(test_client, mission_id=1001, amount=100.0, currency="USD", urgent=False):
    test_client.post("/api/bot/users", json={"telegram_id": 42, "first_name": "Client"})
    _register_provider(test_client, 7, ["service_peinture"], ["Gombe"])
    test_client.post(
        "/api/bot/missions",
        json={
            "telegram_id": 42,
            "mission_id": mission_id,
            "service": "service_peinture",
            "commune": "Gombe",
            "currency": currency,
            "description": "Peindre le salon",
            "urgent": urgent,
        },
    )
    quote_response = test_client.post(
        "/api/bot/quotes",
        json={
            "mission_id": mission_id,
            "provider_telegram_id": 7,
            "amount": amount,
            "currency": currency,
            "delay_hours": 2,
        },
    )
    assert quote_response.status_code == 200
    return quote_response.json()["quote"]["id"]


def test_accepting_a_quote_rejects_the_others_and_confirms_mission(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        quote_id = _setup_mission_with_quote(test_client)
        _register_provider(test_client, 8, ["service_peinture"], ["Gombe"])
        second_quote = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": 1001, "provider_telegram_id": 8, "amount": 90.0, "currency": "USD", "delay_hours": 3},
        ).json()["quote"]

        accept_response = test_client.post(f"/api/bot/quotes/{quote_id}/accept")
        assert accept_response.status_code == 200
        assert accept_response.json()["quote"]["status"] == "accepted"

        rejected = test_client.get("/api/profile/42")
        assert rejected.status_code == 200

        mission = test_client.post("/api/bot/missions/status", json={"mission_id": 1001, "status": "confirmed"}).json()["mission"]
        assert mission["provider_telegram_id"] == 7

        second_quote_after = test_client.post(f"/api/bot/quotes/{second_quote['id']}/reject")
        assert second_quote_after.json()["quote"]["status"] == "rejected"


def test_payment_amounts_use_urgent_commission_rate():
    from backend.app.crud import calculate_payment_amounts

    normal = calculate_payment_amounts(100.0, "USD", urgent=False)
    assert normal["commission_amount"] == 10.0
    assert normal["tola_fee"] == 1.50
    assert normal["total_client"] == 101.50
    assert normal["net_provider"] == 90.0

    urgent = calculate_payment_amounts(100.0, "USD", urgent=True)
    assert urgent["commission_amount"] == 15.0
    assert urgent["net_provider"] == 85.0


def test_cdf_tola_fee_follows_the_live_exchange_rate(monkeypatch):
    import backend.app.crud as crud

    monkeypatch.setattr(crud, "get_usd_to_cdf_rate", lambda: 2000.0)
    amounts = crud.calculate_payment_amounts(100.0, "CDF", urgent=False)
    assert amounts["tola_fee"] == 3000.0  # 1.50 USD * 2000


def test_mission_cannot_start_before_escrow_payment(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        quote_id = _setup_mission_with_quote(test_client)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        response = test_client.post("/api/bot/missions/1001/start", json={"provider_telegram_id": 7})
        assert response.status_code == 400
        assert "escrow" in response.json()["detail"]


def test_full_escrow_and_release_flow(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        pay_response = test_client.post(f"/api/bot/quotes/{quote_id}/pay", json={"operator": "simulation"})
        assert pay_response.status_code == 200
        assert pay_response.json()["mobile_money_ref"] == f"SIM-{quote_id:04d}"

        start_response = test_client.post("/api/bot/missions/1001/start", json={"provider_telegram_id": 7})
        assert start_response.status_code == 200
        assert start_response.json()["mission"]["status"] == "in_progress"

        finish_response = test_client.post("/api/bot/missions/1001/finish", json={"provider_telegram_id": 7})
        assert finish_response.status_code == 200
        assert finish_response.json()["mission"]["status"] == "awaiting_confirmation"

        release_response = test_client.post("/api/bot/missions/1001/release")
        assert release_response.status_code == 200
        released = release_response.json()["mission"]
        assert released["status"] == "completed"
        assert released["payment_status"] == "released"

        provider_profile = test_client.get("/api/profile/7").json()
        assert provider_profile["provider"]["wallet_balance_usd"] == 90.0


def test_wallet_payment_fails_when_balance_insufficient(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        response = test_client.post(f"/api/bot/quotes/{quote_id}/pay-wallet", json={"operator": "wallet"})
        assert response.status_code == 400
        assert "insuffisant" in response.json()["detail"]


def test_wallet_payment_succeeds_and_debits_balance(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        with database_module.SessionLocal() as db:
            from backend.app.models import BotUser

            user = db.get(BotUser, 42)
            user.wallet_balance_usd = 200.0
            db.commit()

        response = test_client.post(f"/api/bot/quotes/{quote_id}/pay-wallet", json={"operator": "wallet"})
        assert response.status_code == 200
        assert response.json()["mobile_money_ref"] == f"WLT-{quote_id:04d}"

        profile = test_client.get("/api/profile/42").json()
        assert profile["client"]["wallet_balance_usd"] == 98.5  # 200 - (100 + 1.50 tola_fee)


def test_consecutive_ignored_auto_pauses_provider_after_three(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        _register_provider(test_client, 9, ["service_peinture"], ["Gombe"])

        for _ in range(2):
            response = test_client.post("/api/bot/providers/9/ignored")
            assert response.json()["provider"]["status"] == "available"

        third_response = test_client.post("/api/bot/providers/9/ignored")
        assert third_response.json()["provider"]["status"] == "paused"
        assert third_response.json()["provider"]["consecutive_ignored"] == 3

        reset_response = test_client.post("/api/bot/providers/9/ignored/reset")
        assert reset_response.json()["provider"]["consecutive_ignored"] == 0


def test_update_user_language(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        test_client.post(
            "/api/bot/users",
            json={"telegram_id": 1, "first_name": "Alice", "phone_number": "+243800000001", "language": "fr"},
        )

        response = test_client.patch("/api/bot/users/1/language", json={"language": "en"})
        assert response.status_code == 200
        assert response.json()["user"]["language"] == "en"

        missing_response = test_client.patch("/api/bot/users/999/language", json={"language": "en"})
        assert missing_response.status_code == 404


def test_update_provider_language(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])

        response = test_client.patch("/api/bot/providers/1/language", json={"language": "ln"})
        assert response.status_code == 200
        assert response.json()["provider"]["language"] == "ln"

        missing_response = test_client.patch("/api/bot/providers/999/language", json={"language": "ln"})
        assert missing_response.status_code == 404
