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
    # Base jetable : tables créées d'un coup (une vraie base passe par Alembic).
    database_module.init_db()
    return backend_main, database_module


def _fund(test_client, mission_id=1001, quote_id=1, amount=100.0, currency="USD", method="mobile_money", urgent=False, client=42, provider=7):
    return test_client.post(
        f"/api/bot/missions/{mission_id}/fund",
        json={
            "method": method,
            "client_telegram_id": client,
            "provider_telegram_id": provider,
            "quote_ref": quote_id,
            "amount": amount,
            "currency": currency,
            "urgent": urgent,
            "service": "service_peinture",
            "commune": "Gombe",
            "description": "Peindre le salon",
        },
    )


def _credit_client_wallet(database_module, telegram_id, amount, currency="USD"):
    from backend.app import ledger

    with database_module.SessionLocal() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
        ledger.record_opening_balance(db, account_id, currency, amount)
        db.commit()


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
        # "pending" dès la création (et non None) : parité avec le défaut SQL
        # de db.py légataire (`status TEXT DEFAULT 'pending'`), et signal
        # nécessaire aux tâches Celery de la Phase 2 (relances : "mission
        # encore sans devis").
        assert create_response.json()["mission"]["status"] == "pending"

        payment_response = _fund(test_client, mission_id=1001)
        assert payment_response.status_code == 200
        assert payment_response.json()["mission"]["status"] == "confirmed"
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

        mission = test_client.get("/api/bot/missions/1001").json()["mission"]
        assert mission["status"] == "confirmed"
        assert mission["provider_telegram_id"] == 7

        second_quote_after = test_client.post(f"/api/bot/quotes/{second_quote['id']}/reject")
        assert second_quote_after.json()["quote"]["status"] == "rejected"


def test_payment_amounts_use_urgent_commission_rate():
    from decimal import Decimal

    from backend.app.ledger import payment_amounts

    normal = payment_amounts(100.0, urgent=False)
    assert normal == {"total": Decimal("100.00"), "commission": Decimal("10.00"), "net": Decimal("90.00")}

    urgent = payment_amounts(100.0, urgent=True)
    assert urgent["commission"] == Decimal("15.00")
    assert urgent["net"] == Decimal("85.00")


def test_client_pays_exactly_the_quote_amount_in_both_currencies():
    """Frais Tola supprimés : le total client == le montant du devis, USD comme CDF."""
    from decimal import Decimal

    from backend.app.ledger import payment_amounts

    assert payment_amounts(100.0, urgent=False)["total"] == Decimal("100.00")
    assert payment_amounts(250000.0, urgent=False)["total"] == Decimal("250000.00")


def test_mission_cannot_start_before_escrow_payment(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        response = test_client.post("/api/bot/missions/1001/start", json={"provider_telegram_id": 7})
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "not_paid"
        assert response.json()["detail"]["mission"]["status"] == "confirmed"


def test_full_escrow_and_release_flow(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        pay_response = _fund(test_client, quote_id=quote_id)
        assert pay_response.status_code == 200
        assert pay_response.json()["money"]["funding"]["reference"] == f"SIM-{quote_id:04d}"
        assert pay_response.json()["money"]["funding"]["net"] == "90.00"

        start_response = test_client.post("/api/bot/missions/1001/start", json={"provider_telegram_id": 7})
        assert start_response.status_code == 200
        assert start_response.json()["mission"]["status"] == "in_progress"

        finish_response = test_client.post("/api/bot/missions/1001/finish", json={"provider_telegram_id": 7})
        assert finish_response.status_code == 200
        assert finish_response.json()["mission"]["status"] == "awaiting_confirmation"

        release_response = test_client.post("/api/bot/missions/1001/confirm", json={"client_telegram_id": 42})
        assert release_response.status_code == 200
        released = release_response.json()["mission"]
        assert released["status"] == "completed"
        assert released["payment_status"] == "released"

        provider_profile = test_client.get("/api/profile/7").json()
        assert provider_profile["provider"]["wallet_balance_usd"] == 90.0
        assert test_client.get("/api/bot/wallets/7").json()["wallet"]["wallet_balance_usd"] == 90.0


def test_wallet_payment_fails_when_balance_insufficient(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        response = _fund(test_client, quote_id=quote_id, method="wallet")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "insufficient_balance"
        assert response.json()["detail"]["mission"]["payment_status"] is None


def test_wallet_payment_succeeds_and_debits_balance(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")
        _credit_client_wallet(database_module, 42, 200.0)

        response = _fund(test_client, quote_id=quote_id, method="wallet")
        assert response.status_code == 200
        assert response.json()["money"]["funding"]["reference"] == f"WLT-{quote_id:04d}"

        profile = test_client.get("/api/profile/42").json()
        assert profile["client"]["wallet_balance_usd"] == 100.0  # 200 - 100 (devis seul, plus de frais Tola)


def test_money_endpoints_return_a_stable_code_and_the_current_mission_on_refusal(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        _fund(test_client, quote_id=quote_id)

        second = _fund(test_client, quote_id=quote_id + 1, amount=50.0)
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "already_paid"
        assert second.json()["detail"]["money"]["funding"]["total"] == "100.00"

        intruder = test_client.post("/api/bot/missions/1001/confirm", json={"client_telegram_id": 999})
        assert intruder.status_code == 403
        assert intruder.json()["detail"]["code"] == "not_mission_client"

        missing = test_client.post("/api/bot/missions/4242/confirm", json={"client_telegram_id": 42})
        assert missing.status_code == 404
        assert missing.json()["detail"] == {"code": "mission_not_found"}


def test_dispute_freezes_funds_and_admin_split_pays_both_parties(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        _fund(test_client, quote_id=quote_id)

        dispute = test_client.post("/api/bot/missions/1001/dispute", json={"client_telegram_id": 42, "reason": "Travail non fait"})
        assert dispute.status_code == 200
        assert dispute.json()["mission"]["status"] == "disputed"
        assert dispute.json()["mission"]["dispute_deadline"] is not None

        frozen = test_client.post("/api/bot/missions/1001/confirm", json={"client_telegram_id": 42})
        assert frozen.status_code == 409
        assert frozen.json()["detail"]["code"] == "mission_disputed"

        resolved = test_client.post(
            "/api/bot/missions/1001/dispute/resolve",
            json={"decision": "split", "provider_percentage": 50, "admin_telegram_id": 1},
        )
        assert resolved.status_code == 200
        assert resolved.json()["mission"]["payment_status"] == "split"
        assert resolved.json()["money"]["settlement"]["provider_amount"] == "45.00"
        assert resolved.json()["money"]["settlement"]["client_amount"] == "45.00"
        assert resolved.json()["money"]["settlement"]["platform_amount"] == "10.00"
        assert test_client.get("/api/bot/wallets/7").json()["wallet"]["wallet_balance_usd"] == 45.0
        assert test_client.get("/api/bot/wallets/42").json()["wallet"]["wallet_balance_usd"] == 45.0

        again = test_client.post(
            "/api/bot/missions/1001/dispute/resolve",
            json={"decision": "refund", "admin_telegram_id": 1},
        )
        assert again.status_code == 409
        assert again.json()["detail"]["code"] == "already_settled"


def test_profile_provider_missions_are_filtered_by_provider_not_client(tmp_path, monkeypatch):
    """Régression backend-parity-auditor : provider_missions réutilisait le
    même filtre que client_missions (BotMission.telegram_id) au lieu de
    filtrer sur provider_telegram_id — un prestataire ne voyait jamais ses
    missions assignées (ou, pire, celles d'un client au même telegram_id)."""
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        quote_id = _setup_mission_with_quote(test_client)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept")

        client_profile = test_client.get("/api/profile/42").json()
        provider_profile = test_client.get("/api/profile/7").json()

        assert len(client_profile["client_missions"]) == 1
        assert len(provider_profile["provider_missions"]) == 1
        assert provider_profile["provider_missions"][0]["mission_id"] == 1001
        assert provider_profile["provider_missions"][0]["client_name"] == "Client"
        assert provider_profile["client_missions"] == [], "7 n'est pas client de la mission 1001"


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
    assert _fund(test_client, mission_id=mission_id, quote_id=quote_id, amount=amount, currency=currency, provider=provider_telegram_id).status_code == 200
    test_client.post(f"/api/bot/missions/{mission_id}/start", json={"provider_telegram_id": provider_telegram_id})
    test_client.post(f"/api/bot/missions/{mission_id}/finish", json={"provider_telegram_id": provider_telegram_id})
    release_response = test_client.post(f"/api/bot/missions/{mission_id}/confirm", json={"client_telegram_id": 42})
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


def test_rank_providers_orders_given_ids_by_score_without_availability_filter(tmp_path, monkeypatch):
    """Matching "mélange" : le bot envoie les prestataires disponibles selon
    db.py ; le backend ne fait que les classer, même s'il les croit
    indisponibles ou sans ce service (changements faits via la Mini App)."""
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        for telegram_id in (1, 2, 3):
            _register_provider(test_client, telegram_id, ["service_peinture"], ["Gombe"])
        with database_module.SessionLocal() as db:
            from backend.app.models import BotProvider

            best = db.get(BotProvider, 3)
            best.average_rating = 5.0
            best.status = "offline"  # périmé : le prestataire s'est remis disponible via la Mini App
            db.get(BotProvider, 2).average_rating = 4.0
            db.commit()

        response = test_client.post("/api/bot/providers/rank", json={"telegram_ids": [1, 2, 3, 999]})

        assert response.status_code == 200
        assert response.json() == {"status": "ok", "telegram_ids": [3, 2, 1]}, "999 inconnu : omis"
        assert set(response.json()) == {"status", "telegram_ids"}, "aucune donnée personnelle renvoyée"
        too_many = test_client.post("/api/bot/providers/rank", json={"telegram_ids": list(range(101))})
        assert too_many.status_code == 422


def test_wallet_refusal_on_a_mission_the_backend_never_saw_returns_409_not_500(tmp_path, monkeypatch):
    """La mission est créée par la demande de paiement elle-même ; refusée,
    elle disparaît avec la transaction : la réponse reste un refus propre."""
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        response = _fund(test_client, mission_id=555, method="wallet")

        assert response.status_code == 409
        assert response.json()["detail"] == {"code": "insufficient_balance"}
        assert test_client.get("/api/bot/missions/555").status_code == 404


def test_backend_refuses_a_quote_from_the_mission_client(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _setup_mission_with_quote(test_client)
        _register_provider(test_client, 42, ["service_peinture"], ["Gombe"])
        response = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": 1001, "provider_telegram_id": 42, "amount": 10.0, "currency": "USD", "delay_hours": 1},
        )

        assert response.status_code == 409
        assert response.json()["detail"] == {"code": "provider_is_client"}
