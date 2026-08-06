import importlib
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.main import app

client = TestClient(app)

# Clé factice utilisée par tous les tests authentifiés - jamais la vraie
# BACKEND_API_KEY de .env, qui n'est ni lue ni nécessaire ici.
TEST_API_KEY = "test-backend-api-key-not-a-secret"


def _reload_backend_with_db(monkeypatch, tmp_path, name="test_backend.db"):
    db_path = tmp_path / name
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BACKEND_API_KEY", TEST_API_KEY)

    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    return backend_main, database_module


def _authed_client(backend_main):
    """TestClient qui envoie X-API-Key sur chaque requête, sans toucher aux
    54 appels test_client.get/post/patch existants."""
    test_client = TestClient(backend_main.app)
    test_client.headers["X-API-Key"] = TEST_API_KEY
    return test_client


def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_profile_endpoint_returns_payload_for_telegram_id(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        response = test_client.get("/api/profile/12345")
        assert response.status_code == 200
        payload = response.json()
        assert payload["telegram_id"] == 12345
        assert "client" in payload
        assert "provider" in payload


def test_backend_state_persists_to_db(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
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

    with _authed_client(backend_main) as test_client:
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

    with _authed_client(backend_main) as test_client:
        plumbing = _register_provider(test_client, 1, ["service_plomberie"], ["Gombe"])
        assert plumbing["module"] == "B"

        painting = _register_provider(test_client, 2, ["service_peinture"], ["Gombe"])
        assert painting["module"] == "A"


def test_provider_registration_resets_status_on_update(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
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

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])  # matches, default score
        _register_provider(test_client, 2, ["service_peinture"], ["Kintambo"])  # wrong commune
        _register_provider(test_client, 3, ["service_plomberie"], ["Gombe"])  # wrong service
        _register_provider(test_client, 4, ["service_peinture"], ["Gombe"])  # low score
        _register_provider(test_client, 5, ["service_peinture"], ["Gombe"])  # high score

        with database_module.SessionLocal() as db:
            from backend.app.models import BotProvider

            low = db.get(BotProvider, 4)
            low.badge = "pending"
            low.average_rating = 1.0
            high = db.get(BotProvider, 5)
            high.badge = "partner"
            high.average_rating = 5.0
            high.success_rate = 100
            high.total_missions = 10  # au-delà du seuil : le bonus fiabilité s'applique
            db.commit()

        response = test_client.get("/api/bot/providers/matching", params={"service": "service_peinture", "commune": "Gombe"})
        assert response.status_code == 200
        matches = response.json()["providers"]
        assert [p["telegram_id"] for p in matches] == [5, 4, 1]


def test_perfect_success_rate_gives_no_bonus_without_enough_missions(tmp_path, monkeypatch):
    """Un prestataire sans historique ne doit pas être classé comme un vétéran irréprochable."""
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])  # neuf, success_rate 100 par défaut
        _register_provider(test_client, 2, ["service_peinture"], ["Gombe"])  # expérimenté

        with database_module.SessionLocal() as db:
            from backend.app.models import BotProvider

            veteran = db.get(BotProvider, 2)
            veteran.success_rate = 100.0
            veteran.total_missions = 5
            db.commit()

        response = test_client.get(
            "/api/bot/providers/matching", params={"service": "service_peinture", "commune": "Gombe"}
        )
        assert [p["telegram_id"] for p in response.json()["providers"]][0] == 2


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

    with _authed_client(backend_main) as test_client:
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
    assert normal["tola_fee"] == 0.00
    assert normal["total_client"] == 100.00
    assert normal["net_provider"] == 90.0

    urgent = calculate_payment_amounts(100.0, "USD", urgent=True)
    assert urgent["commission_amount"] == 15.0
    assert urgent["net_provider"] == 85.0


def test_client_pays_exactly_the_quote_amount_in_both_currencies():
    """Frais Tola supprimés : le total client == le montant du devis, USD comme CDF."""
    from backend.app.crud import calculate_payment_amounts

    usd = calculate_payment_amounts(100.0, "USD", urgent=False)
    cdf = calculate_payment_amounts(250000.0, "CDF", urgent=False)

    assert usd["total_client"] == 100.0
    assert cdf["total_client"] == 250000.0
    assert usd["tola_fee"] == 0.0
    assert cdf["tola_fee"] == 0.0
    assert usd["aggregator_fee"] == 0.0
    assert cdf["aggregator_fee"] == 0.0


def test_mission_cannot_start_before_escrow_payment(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        response = test_client.post("/api/bot/missions/1001/start", json={"provider_telegram_id": 7})
        assert response.status_code == 400
        assert "escrow" in response.json()["detail"]


def test_full_escrow_and_release_flow(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
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

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        response = test_client.post(f"/api/bot/quotes/{quote_id}/pay-wallet", json={"operator": "wallet"})
        assert response.status_code == 400
        assert "insuffisant" in response.json()["detail"]


def test_wallet_payment_succeeds_and_debits_balance(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
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
        assert profile["client"]["wallet_balance_usd"] == 100.0  # 200 - 100 (devis seul, plus de frais Tola)


def test_consecutive_ignored_auto_pauses_provider_after_three(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
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

    with _authed_client(backend_main) as test_client:
        test_client.post(
            "/api/bot/users",
            json={"telegram_id": 1, "first_name": "Alice", "phone_number": "+243800000001", "language": "fr"},
        )

        response = test_client.patch("/api/bot/users/1/language", json={"language": "en"})
        assert response.status_code == 200
        assert response.json()["user"]["language"] == "en"

        missing_response = test_client.patch("/api/bot/users/999/language", json={"language": "en"})
        assert missing_response.status_code == 404


def _complete_mission_flow(test_client, mission_id=1001, amount=100.0, currency="USD", provider_telegram_id=7):
    quote_id = _setup_mission_with_quote(test_client, mission_id=mission_id, amount=amount, currency=currency)
    test_client.post(f"/api/bot/quotes/{quote_id}/accept")
    test_client.post(f"/api/bot/quotes/{quote_id}/pay", json={"operator": "simulation"})
    test_client.post(f"/api/bot/missions/{mission_id}/start", json={"provider_telegram_id": provider_telegram_id})
    test_client.post(f"/api/bot/missions/{mission_id}/finish", json={"provider_telegram_id": provider_telegram_id})
    release_response = test_client.post(f"/api/bot/missions/{mission_id}/release")
    assert release_response.status_code == 200
    return quote_id


def test_review_creation_updates_provider_average_and_total_reviews(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)
        first = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": 1001, "client_telegram_id": 42, "rating": 5, "comment": "Top"},
        )
        assert first.status_code == 200
        assert first.json()["review"]["rating"] == 5

        _complete_mission_flow(test_client, mission_id=1002)
        second = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": 1002, "client_telegram_id": 42, "rating": 3},
        )
        assert second.status_code == 200

        provider_profile = test_client.get("/api/profile/7").json()
        assert provider_profile["provider"]["average_rating"] == 4.0
        assert provider_profile["provider"]["total_reviews"] == 2


def test_review_rejected_for_duplicate_mission(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)
        test_client.post("/api/bot/reviews", json={"mission_id": 1001, "client_telegram_id": 42, "rating": 4})

        duplicate = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": 1001, "client_telegram_id": 42, "rating": 2},
        )
        assert duplicate.status_code == 400
        assert "déjà été évaluée" in duplicate.json()["detail"]


def test_review_rejected_for_rating_out_of_range(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)

        too_low = test_client.post("/api/bot/reviews", json={"mission_id": 1001, "client_telegram_id": 42, "rating": 0})
        assert too_low.status_code == 400
        assert "1 et 5" in too_low.json()["detail"]

        too_high = test_client.post("/api/bot/reviews", json={"mission_id": 1001, "client_telegram_id": 42, "rating": 6})
        assert too_high.status_code == 400
        assert "1 et 5" in too_high.json()["detail"]


def test_review_rejected_for_mismatched_client(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)

        response = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": 1001, "client_telegram_id": 999, "rating": 5},
        )
        assert response.status_code == 400
        assert "associé" in response.json()["detail"]


def test_update_provider_language(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])

        response = test_client.patch("/api/bot/providers/1/language", json={"language": "ln"})
        assert response.status_code == 200
        assert response.json()["provider"]["language"] == "ln"

        missing_response = test_client.patch("/api/bot/providers/999/language", json={"language": "ln"})
        assert missing_response.status_code == 404


# ── Statistiques prestataire et badges (Phase 1) ────────────────


def _rate(test_client, mission_id, rating, client_telegram_id=42):
    return test_client.post(
        "/api/bot/reviews",
        json={"mission_id": mission_id, "client_telegram_id": client_telegram_id, "rating": rating},
    )


def _provider_stats(test_client, provider_telegram_id=7):
    return test_client.get(f"/api/profile/{provider_telegram_id}").json()["provider"]


def test_completing_a_mission_counts_towards_total_missions(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)
        assert _provider_stats(test_client)["total_missions"] == 1

        _complete_mission_flow(test_client, mission_id=1002)
        assert _provider_stats(test_client)["total_missions"] == 2


def test_success_rate_is_100_when_nothing_has_failed(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)
        assert _provider_stats(test_client)["success_rate"] == 100.0


def test_a_disputed_mission_lowers_the_success_rate(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client, mission_id=1001)
        _complete_mission_flow(test_client, mission_id=1002)
        _complete_mission_flow(test_client, mission_id=1003)

        # Une des trois part en litige, puis on redéclenche un recalcul.
        from backend.app import crud
        from backend.app.models import BotMission

        with database_module.SessionLocal() as db:
            db.get(BotMission, 1003).status = "disputed"
            db.commit()
            crud._recompute_provider_stats(db, 7)

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 2
        assert stats["success_rate"] == round(2 / 3 * 100, 2)


def test_provider_earns_premium_badge_at_five_missions_and_good_rating(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        for index in range(5):
            mission_id = 2000 + index
            _complete_mission_flow(test_client, mission_id=mission_id)
            _rate(test_client, mission_id, 5)

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 5
        assert stats["average_rating"] == 5.0
        assert stats["badge"] == "premium"


def test_badge_stays_below_premium_when_rating_is_too_low(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        for index in range(5):
            mission_id = 2100 + index
            _complete_mission_flow(test_client, mission_id=mission_id)
            _rate(test_client, mission_id, 3)  # moyenne 3.0 < 4.0

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 5
        assert stats["badge"] == "pending"


def test_badge_falls_back_to_verified_when_no_tier_is_earned(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 7, ["service_plomberie"], ["Gombe"])
        assert test_client.post("/api/bot/providers/7/verify").status_code == 200

        _complete_mission_flow(test_client, mission_id=2200)
        _rate(test_client, 2200, 5)

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 1  # trop peu pour premium
        assert stats["badge"] == "verified"


def test_a_new_provider_has_no_badge_tier(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 7, ["service_plomberie"], ["Gombe"])
        stats = _provider_stats(test_client)
        assert stats["badge"] == "pending"
        assert stats["total_missions"] == 0


# ── Authentification backend (X-API-Key) ────────────────────────


def test_request_without_api_key_is_rejected(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        response = test_client.get("/api/profile/12345")
        assert response.status_code == 401


def test_request_with_wrong_api_key_is_rejected(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        response = test_client.get(
            "/api/profile/12345",
            headers={"X-API-Key": "guessed-wrong-key"},
        )
        assert response.status_code == 401


def test_request_with_correct_api_key_is_accepted(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        response = test_client.get("/api/profile/12345")
        assert response.status_code == 200


def test_health_endpoint_needs_no_api_key(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with TestClient(backend_main.app) as test_client:
        response = test_client.get("/health")
        assert response.status_code == 200


# ── Vérification / suspension prestataire ───────────────────────


def test_verify_provider_endpoint_sets_is_verified(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])

        response = test_client.post("/api/bot/providers/1/verify")
        assert response.status_code == 200
        assert response.json()["provider"]["is_verified"] is True


def test_suspend_then_unsuspend_provider(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 1, ["service_peinture"], ["Gombe"])

        suspend_response = test_client.post("/api/bot/providers/1/suspend")
        assert suspend_response.status_code == 200
        assert suspend_response.json()["provider"]["is_suspended"] is True
        assert suspend_response.json()["provider"]["status"] == "paused"

        unsuspend_response = test_client.post("/api/bot/providers/1/unsuspend")
        assert unsuspend_response.status_code == 200
        assert unsuspend_response.json()["provider"]["is_suspended"] is False
        assert unsuspend_response.json()["provider"]["status"] == "available"


def test_verify_unknown_provider_returns_404(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        response = test_client.post("/api/bot/providers/999999/verify")
        assert response.status_code == 404
