import importlib
import itertools
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


def _fund(test_client, mission_id, quote_id, method="mobile_money", client=42):
    """Le client 42 accepte le devis (rejeu sans effet s'il l'est déjà), puis
    `client` paie la mission sur ce devis. Mobile Money : par une intention de
    paiement, confirmée ici tout de suite par l'agrégateur simulé ; wallet :
    paiement direct. Montant et prestataire sont ceux du devis."""
    test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))
    path = "fund" if method == "wallet" else "payment-intents"
    payload = {"method": "wallet", "quote_id": quote_id} if method == "wallet" else {
        "quote_id": quote_id, "phone": "+243810000000", "operator": "mpesa"
    }
    return test_client.post(f"/api/bot/missions/{mission_id}/{path}", json=payload, headers=_as(client))


def _credit_client_wallet(database_module, telegram_id, amount, currency="USD"):
    from backend.app import ledger

    with database_module.SessionLocal() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
        ledger.record_opening_balance(db, account_id, currency, amount)
        db.commit()



def _as(telegram_id):
    """En-têtes d'une action faite au nom d'une personne connue par Telegram."""
    return {"X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}

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
        mission_id, quote_id = _setup_mission_with_quote(test_client, urgent=True)
        # "pending" dès la création (et non None) : parité avec le défaut SQL
        # de db.py légataire (`status TEXT DEFAULT 'pending'`), et signal
        # nécessaire aux tâches Celery de la Phase 2 (relances : "mission
        # encore sans devis"). Après le devis : "quoted".
        assert test_client.get(f"/api/bot/missions/{mission_id}", headers=_as(42)).json()["mission"]["status"] == "quoted"

        payment_response = _fund(test_client, mission_id=mission_id, quote_id=quote_id)
        assert payment_response.status_code == 200
        assert payment_response.json()["mission"]["status"] == "confirmed"
        assert payment_response.json()["mission"]["payment_status"] == "paid_escrow"
        # Urgence lue sur la mission : commission de 15 %.
        assert payment_response.json()["money"]["funding"]["commission"] == "15.00"

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


_CREATION_KEYS = itertools.count(1)


def _create_mission(test_client, client=42, alert=(7,), key=None, **fields):
    """Mission créée par le backend pour le client `client`, avec les
    prestataires `alert` prévenus. Renvoie son numéro, attribué par le backend."""
    payload = {
        "creation_key": key or f"demande-{next(_CREATION_KEYS)}",
        "service": "service_peinture",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Peindre le salon",
        "urgent": False,
        "alert_provider_telegram_ids": list(alert),
        **fields,
    }
    response = test_client.post("/api/bot/missions", json=payload, headers=_as(client))
    assert response.status_code == 200, response.json()
    return response.json()["mission"]["mission_id"]


def _setup_mission_with_quote(test_client, amount=100.0, currency="USD", urgent=False):
    test_client.post("/api/bot/users", json={"telegram_id": 42, "first_name": "Client"})
    _register_provider(test_client, 7, ["service_peinture"], ["Gombe"])
    mission_id = _create_mission(test_client, alert=(7, 8), currency=currency, urgent=urgent)
    quote_response = test_client.post(
        "/api/bot/quotes",
        json={
            "mission_id": mission_id,
            "amount": amount,
            "currency": currency,
            "delay_hours": 2,
        },
        headers=_as(7),
    )
    assert quote_response.status_code == 200
    return mission_id, quote_response.json()["quote"]["id"]


def test_accepting_a_quote_rejects_the_others_and_confirms_mission(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client)
        _register_provider(test_client, 8, ["service_peinture"], ["Gombe"])
        second_quote = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 90.0, "currency": "USD", "delay_hours": 3},
            headers=_as(8),
        ).json()["quote"]

        accept_response = test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))
        assert accept_response.status_code == 200
        assert accept_response.json()["quote"]["status"] == "accepted"

        rejected = test_client.get("/api/profile/42")
        assert rejected.status_code == 200

        mission = test_client.get(f"/api/bot/missions/{mission_id}", headers=_as(42)).json()["mission"]
        assert mission["status"] == "confirmed"
        assert mission["provider_telegram_id"] == 7

        second_quote_after = test_client.post(f"/api/bot/quotes/{second_quote['id']}/reject", headers=_as(42))
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
        mission_id, quote_id = _setup_mission_with_quote(test_client)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))

        response = test_client.post(f"/api/bot/missions/{mission_id}/start", headers=_as(7))
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "not_paid"
        assert response.json()["detail"]["mission"]["status"] == "confirmed"


def test_full_escrow_and_release_flow(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))

        pay_response = _fund(test_client, mission_id=mission_id, quote_id=quote_id)
        assert pay_response.status_code == 200
        assert pay_response.json()["intent"]["status"] == "succeeded"
        assert pay_response.json()["money"]["funding"]["reference"] == "SIM-PAY-000001"
        assert pay_response.json()["money"]["funding"]["net"] == "90.00"

        start_response = test_client.post(f"/api/bot/missions/{mission_id}/start", headers=_as(7))
        assert start_response.status_code == 200
        assert start_response.json()["mission"]["status"] == "in_progress"

        finish_response = test_client.post(f"/api/bot/missions/{mission_id}/finish", headers=_as(7))
        assert finish_response.status_code == 200
        assert finish_response.json()["mission"]["status"] == "awaiting_confirmation"

        release_response = test_client.post(f"/api/bot/missions/{mission_id}/confirm", headers=_as(42))
        assert release_response.status_code == 200
        released = release_response.json()["mission"]
        assert released["status"] == "completed"
        assert released["payment_status"] == "released"

        provider_profile = test_client.get("/api/profile/7").json()
        assert provider_profile["provider"]["wallet_balance_usd"] == 90.0
        assert test_client.get("/api/me/wallet", headers=_as(7)).json()["wallet"]["wallet_balance_usd"] == 90.0


def test_wallet_payment_fails_when_balance_insufficient(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))

        response = _fund(test_client, mission_id=mission_id, quote_id=quote_id, method="wallet")
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "insufficient_balance"
        assert response.json()["detail"]["mission"]["payment_status"] is None


def test_wallet_payment_succeeds_and_debits_balance(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))
        _credit_client_wallet(database_module, 42, 200.0)

        response = _fund(test_client, mission_id=mission_id, quote_id=quote_id, method="wallet")
        assert response.status_code == 200
        assert response.json()["money"]["funding"]["reference"] == f"WLT-{quote_id:04d}"

        profile = test_client.get("/api/profile/42").json()
        assert profile["client"]["wallet_balance_usd"] == 100.0  # 200 - 100 (devis seul, plus de frais Tola)


def test_money_endpoints_return_a_stable_code_and_the_current_mission_on_refusal(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        _fund(test_client, mission_id=mission_id, quote_id=quote_id)

        second = _fund(test_client, mission_id=mission_id, quote_id=quote_id + 1)
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "already_paid"
        assert second.json()["detail"]["money"]["funding"]["total"] == "100.00"

        intruder = test_client.post(f"/api/bot/missions/{mission_id}/confirm", headers=_as(999))
        assert intruder.status_code == 403
        assert intruder.json()["detail"]["code"] == "not_mission_client"

        missing = test_client.post("/api/bot/missions/4242/confirm", headers=_as(42))
        assert missing.status_code == 404
        assert missing.json()["detail"] == {"code": "mission_not_found"}


def test_dispute_freezes_funds_and_admin_split_pays_both_parties(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client, amount=100.0)
        _fund(test_client, mission_id=mission_id, quote_id=quote_id)

        dispute = test_client.post(f"/api/bot/missions/{mission_id}/dispute", json={"reason": "Travail non fait"}, headers=_as(42))
        assert dispute.status_code == 200
        assert dispute.json()["mission"]["status"] == "disputed"
        assert dispute.json()["mission"]["dispute_deadline"] is not None

        frozen = test_client.post(f"/api/bot/missions/{mission_id}/confirm", headers=_as(42))
        assert frozen.status_code == 409
        assert frozen.json()["detail"]["code"] == "mission_disputed"

        not_admin = test_client.post(
            f"/api/bot/missions/{mission_id}/dispute/resolve",
            json={"decision": "refund"},
            headers=_as(42),
        )
        assert not_admin.status_code == 403
        assert not_admin.json()["detail"] == {"code": "not_admin"}

        resolved = test_client.post(
            f"/api/bot/missions/{mission_id}/dispute/resolve",
            json={"decision": "split", "provider_percentage": 50},
            headers=_as(1),
        )
        assert resolved.status_code == 200
        assert resolved.json()["mission"]["payment_status"] == "split"
        assert resolved.json()["money"]["settlement"]["provider_amount"] == "45.00"
        assert resolved.json()["money"]["settlement"]["client_amount"] == "45.00"
        assert resolved.json()["money"]["settlement"]["platform_amount"] == "10.00"
        assert test_client.get("/api/me/wallet", headers=_as(7)).json()["wallet"]["wallet_balance_usd"] == 45.0
        assert test_client.get("/api/me/wallet", headers=_as(42)).json()["wallet"]["wallet_balance_usd"] == 45.0

        again = test_client.post(
            f"/api/bot/missions/{mission_id}/dispute/resolve",
            json={"decision": "refund"},
            headers=_as(1),
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
        mission_id, quote_id = _setup_mission_with_quote(test_client)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))

        client_profile = test_client.get("/api/profile/42").json()
        provider_profile = test_client.get("/api/profile/7").json()

        assert len(client_profile["client_missions"]) == 1
        assert len(provider_profile["provider_missions"]) == 1
        assert provider_profile["provider_missions"][0]["mission_id"] == mission_id
        assert provider_profile["provider_missions"][0]["client_name"] == "Client"
        assert provider_profile["client_missions"] == [], "7 n'est pas client de cette mission"


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


def _complete_mission_flow(test_client, amount=100.0, currency="USD", provider_telegram_id=7):
    mission_id, quote_id = _setup_mission_with_quote(test_client, amount=amount, currency=currency)
    test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))
    assert _fund(test_client, mission_id=mission_id, quote_id=quote_id).status_code == 200
    test_client.post(f"/api/bot/missions/{mission_id}/start", headers=_as(provider_telegram_id))
    test_client.post(f"/api/bot/missions/{mission_id}/finish", headers=_as(provider_telegram_id))
    release_response = test_client.post(f"/api/bot/missions/{mission_id}/confirm", headers=_as(42))
    assert release_response.status_code == 200
    return mission_id


def test_review_creation_updates_provider_average_and_total_reviews(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _complete_mission_flow(test_client)
        first = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": mission_id, "rating": 5, "comment": "Top"},
            headers=_as(42),
        )
        assert first.status_code == 200
        assert first.json()["review"]["rating"] == 5

        second_mission_id = _complete_mission_flow(test_client)
        second = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": second_mission_id, "rating": 3},
            headers=_as(42),
        )
        assert second.status_code == 200

        provider_profile = test_client.get("/api/profile/7").json()
        assert provider_profile["provider"]["average_rating"] == 4.0
        assert provider_profile["provider"]["total_reviews"] == 2


def test_review_rejected_for_duplicate_mission(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _complete_mission_flow(test_client)
        test_client.post("/api/bot/reviews", json={"mission_id": mission_id, "rating": 4}, headers=_as(42))

        duplicate = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": mission_id, "rating": 2},
            headers=_as(42),
        )
        assert duplicate.status_code == 400
        assert "déjà été évaluée" in duplicate.json()["detail"]


def test_review_rejected_for_rating_out_of_range(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _complete_mission_flow(test_client)

        too_low = test_client.post("/api/bot/reviews", json={"mission_id": mission_id, "rating": 0}, headers=_as(42))
        assert too_low.status_code == 400
        assert "1 et 5" in too_low.json()["detail"]

        too_high = test_client.post("/api/bot/reviews", json={"mission_id": mission_id, "rating": 6}, headers=_as(42))
        assert too_high.status_code == 400
        assert "1 et 5" in too_high.json()["detail"]


def test_review_rejected_for_mismatched_client(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _complete_mission_flow(test_client)

        response = test_client.post(
            "/api/bot/reviews",
            json={"mission_id": mission_id, "rating": 5},
            headers=_as(999),
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
        json={"mission_id": mission_id, "rating": rating},
        headers=_as(client_telegram_id),
    )


def _provider_stats(test_client, provider_telegram_id=7):
    return test_client.get(f"/api/profile/{provider_telegram_id}").json()["provider"]


def test_completing_a_mission_counts_towards_total_missions(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _complete_mission_flow(test_client)
        assert _provider_stats(test_client)["total_missions"] == 1

        _complete_mission_flow(test_client)
        assert _provider_stats(test_client)["total_missions"] == 2


def test_success_rate_is_100_when_nothing_has_failed(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _complete_mission_flow(test_client)
        assert _provider_stats(test_client)["success_rate"] == 100.0


def test_a_disputed_mission_lowers_the_success_rate(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client)
        _complete_mission_flow(test_client)
        disputed_id = _complete_mission_flow(test_client)

        # Une des trois part en litige, puis on redéclenche un recalcul.
        from backend.app import crud
        from backend.app.models import BotMission

        with database_module.SessionLocal() as db:
            db.get(BotMission, disputed_id).status = "disputed"
            db.commit()
            crud._recompute_provider_stats(db, 7)

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 2
        assert stats["success_rate"] == round(2 / 3 * 100, 2)


def test_provider_earns_premium_badge_at_five_missions_and_good_rating(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        for index in range(5):
            mission_id = _complete_mission_flow(test_client)
            _rate(test_client, mission_id, 5)

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 5
        assert stats["average_rating"] == 5.0
        assert stats["badge"] == "premium"


def test_badge_stays_below_premium_when_rating_is_too_low(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        for index in range(5):
            mission_id = _complete_mission_flow(test_client)
            _rate(test_client, mission_id, 3)  # moyenne 3.0 < 4.0

        stats = _provider_stats(test_client)
        assert stats["total_missions"] == 5
        assert stats["badge"] == "pending"


def test_badge_falls_back_to_verified_when_no_tier_is_earned(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _register_provider(test_client, 7, ["service_plomberie"], ["Gombe"])
        assert test_client.post("/api/bot/providers/7/verify").status_code == 200

        mission_id = _complete_mission_flow(test_client)
        _rate(test_client, mission_id, 5)

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


def test_a_payment_never_creates_a_mission(tmp_path, monkeypatch):
    """Payer une mission que le backend ne connaît pas : refus propre, rien
    n'est créé (avant, la demande de paiement créait la mission)."""
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _credit_client_wallet(database_module, 42, 500.0)

    with _authed_client(backend_main) as test_client:
        wallet = test_client.post("/api/bot/missions/555/fund", json={"method": "wallet", "quote_id": 1}, headers=_as(42))
        intent = test_client.post(
            "/api/bot/missions/555/payment-intents",
            json={"quote_id": 1, "phone": "+243810000000", "operator": "mpesa"},
            headers=_as(42),
        )

        assert wallet.status_code == intent.status_code == 404
        assert wallet.json()["detail"] == intent.json()["detail"] == {"code": "mission_not_found"}
        assert test_client.get("/api/bot/missions/555", headers=_as(42)).status_code == 404


def test_the_channel_cannot_choose_the_amount_or_the_provider(tmp_path, monkeypatch):
    """Les anciens champs (montant, prestataire, devis du bot) sont ignorés :
    le montant payé est celui du devis accepté."""
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _credit_client_wallet(database_module, 42, 500.0)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client, amount=80.0)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42))
        response = test_client.post(
            f"/api/bot/missions/{mission_id}/fund",
            json={"method": "wallet", "quote_id": quote_id, "amount": 1.0, "provider_telegram_id": 42, "quote_ref": 99},
            headers=_as(42),
        )

        assert response.status_code == 200
        assert response.json()["money"]["funding"]["total"] == "80.00"
        assert response.json()["mission"]["provider_telegram_id"] == 7


def test_a_quote_must_be_accepted_before_payment(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _credit_client_wallet(database_module, 42, 500.0)

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client)
        response = test_client.post(
            f"/api/bot/missions/{mission_id}/fund", json={"method": "wallet", "quote_id": quote_id}, headers=_as(42)
        )
        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "quote_not_accepted"


def test_only_one_quote_is_accepted_and_it_cannot_be_withdrawn(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, first = _setup_mission_with_quote(test_client)
        _register_provider(test_client, 8, ["service_peinture"], ["Gombe"])
        second = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 90.0, "currency": "USD", "delay_hours": 3},
            headers=_as(8),
        ).json()["quote"]["id"]

        assert test_client.post(f"/api/bot/quotes/{first}/accept", headers=_as(42)).status_code == 200
        assert test_client.post(f"/api/bot/quotes/{first}/accept", headers=_as(42)).status_code == 200, "rejeu"
        assert test_client.post(f"/api/bot/quotes/{second}/accept", headers=_as(42)).json()["detail"] == {"code": "quote_not_open"}
        assert test_client.post(f"/api/bot/quotes/{first}/reject", headers=_as(42)).json()["detail"] == {"code": "quote_not_open"}
        late = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 70.0, "currency": "USD", "delay_hours": 1},
            headers=_as(8),
        )
        assert late.json()["detail"] == {"code": "mission_not_open"}


def test_backend_refuses_a_quote_from_the_mission_client(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id, _ = _setup_mission_with_quote(test_client)
        _register_provider(test_client, 42, ["service_peinture"], ["Gombe"])
        response = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 10.0, "currency": "USD", "delay_hours": 1},
            headers=_as(42),
        )

        assert response.status_code == 409
        assert response.json()["detail"] == {"code": "provider_is_client"}


def test_mobile_money_cannot_be_declared_paid_by_the_bot(tmp_path, monkeypatch):
    """Seul l'agrégateur confirme un paiement Mobile Money : /fund le refuse."""
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        response = test_client.post(
            "/api/bot/missions/1/fund",
            json={"method": "mobile_money", "quote_id": 1},
            headers=_as(42),
        )
        assert response.status_code == 400
        assert response.json()["detail"] == {"code": "use_payment_intent"}


def test_payout_endpoints_hold_then_pay_after_admin_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "1")
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        _complete_mission_flow(test_client)  # le prestataire 7 gagne 90 USD
        payout = {"amount": 50.0, "currency": "USD", "phone": "+243970000000", "operator": "airtel"}

        requested = test_client.post("/api/bot/payouts", json=payout, headers=_as(7)).json()["payout"]
        assert requested["status"] == "awaiting_approval"
        assert test_client.get("/api/me/wallet", headers=_as(7)).json()["wallet"]["wallet_balance_usd"] == 40.0
        assert test_client.get("/api/bot/payouts", headers=_as(7)).status_code == 403, "liste réservée à l'admin"
        assert [p["id"] for p in test_client.get("/api/bot/payouts", headers=_as(1)).json()["payouts"]] == [requested["id"]]

        for decision in ("approve", "reject"):
            refused = test_client.post(f"/api/bot/payouts/{requested['id']}/{decision}", json={}, headers=_as(7))
            assert refused.status_code == 403
            assert refused.json()["detail"] == {"code": "not_admin"}

        approved = test_client.post(f"/api/bot/payouts/{requested['id']}/approve", json={}, headers=_as(1))
        assert approved.json()["payout"]["status"] == "succeeded"

        too_much = test_client.post("/api/bot/payouts", json={**payout, "amount": 100.0}, headers=_as(7))
        assert too_much.status_code == 409
        assert too_much.json()["detail"] == {"code": "insufficient_balance"}


def test_webhook_without_a_valid_signature_is_refused(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        response = test_client.post("/api/payments/webhook/simulation", content=b'{"reference": "SIM-PAY-000001"}')
        assert response.status_code == 401
        assert test_client.post("/api/payments/webhook/flexpay", content=b"{}").status_code == 404


def test_payment_intents_name_the_parties_by_account(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    from backend.app import ledger
    from backend.app.models import PaymentIntent

    with _authed_client(backend_main) as test_client:
        mission_id, quote_id = _setup_mission_with_quote(test_client)
        assert _fund(test_client, mission_id=mission_id, quote_id=quote_id).status_code == 200
    with database_module.SessionLocal() as db:
        request = db.query(PaymentIntent).one().funding_request
        assert request["quote_id"] == quote_id
        assert "amount" not in request, "le montant est relu dans le devis, jamais gardé de la demande"
        assert request["client_account_id"] == ledger.account_id_for(db, ledger.TELEGRAM, 42)
        assert request["provider_account_id"] == ledger.account_id_for(db, ledger.TELEGRAM, 7)
        assert "client_telegram_id" not in request and "provider_telegram_id" not in request


# ── Acteur : identité de canal résolue par le backend ───────────


def test_actions_without_a_valid_actor_are_refused(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        missing = test_client.post("/api/bot/missions/1/confirm")
        assert missing.status_code == 400
        assert missing.json()["detail"] == {"code": "actor_required"}
        unknown = test_client.post(
            "/api/bot/missions/1/confirm", headers={"X-Actor-Channel": "sms", "X-Actor-Id": "42"}
        )
        assert unknown.json()["detail"] == {"code": "unknown_channel"}
        # L'acteur `app` ne naît que d'une session vérifiée par l'API publique :
        # l'API des canaux de confiance ne l'accepte jamais par en-têtes.
        as_app = test_client.post(
            "/api/bot/missions/1/confirm", headers={"X-Actor-Channel": "app", "X-Actor-Id": "x" * 32}
        )
        assert as_app.status_code == 400
        assert as_app.json()["detail"] == {"code": "unknown_channel"}
        forged = test_client.post("/api/bot/missions/1/confirm", headers={"X-Actor-Channel": "telegram", "X-Actor-Id": "42 OR 1"})
        assert forged.json()["detail"] == {"code": "invalid_actor"}


def test_only_the_mission_client_accepts_or_rejects_its_quotes(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)

    with _authed_client(backend_main) as test_client:
        mission_id = _create_mission(test_client, service="s")
        quote_id = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 90.0, "currency": "USD", "delay_hours": 3},
            headers=_as(7),
        ).json()["quote"]["id"]

        for action in ("accept", "reject"):
            intruder = test_client.post(f"/api/bot/quotes/{quote_id}/{action}", headers=_as(7))
            assert intruder.status_code == 403
            assert intruder.json()["detail"] == {"code": "not_mission_client"}
        assert test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(42)).json()["quote"]["status"] == "accepted"


def test_a_wallet_is_only_read_by_its_owner(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _credit_client_wallet(database_module, 42, 30.0)

    with _authed_client(backend_main) as test_client:
        assert test_client.get("/api/me/wallet", headers=_as(42)).json()["wallet"]["wallet_balance_usd"] == 30.0
        assert test_client.get("/api/me/wallet", headers=_as(7)).json()["wallet"]["wallet_balance_usd"] == 0.0
        assert test_client.get("/api/bot/wallets/42").status_code == 404, "plus de lecture du wallet d'autrui"
