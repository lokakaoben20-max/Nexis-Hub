"""Tests de la Mini App Telegram (mini_app/app.py).

Le coeur de ces tests est la validation de `initData` : c'est la seule barrière
entre la Mini App et n'importe qui sachant construire une requête HTTP. Elle
n'avait aucune couverture jusqu'ici, alors qu'un refactor qui l'affaiblit
(comparaison non constante, hash calculé sur les mauvais champs, expiration
sautée) ne se verrait ni à l'exécution ni à la lecture.
"""

import hashlib
import hmac
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import db
from mini_app import app as mini_app_module

TEST_TOKEN = "123456:TEST-TOKEN-NOT-A-REAL-BOT"
CLIENT_ID = 4242
OTHER_ID = 9999


def _build_init_data(user_id: int, token: str = TEST_TOKEN, auth_date: int | None = None) -> str:
    """Fabrique un initData signé comme le ferait Telegram."""
    fields = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAtest-query-id",
        "user": json.dumps({"id": user_id, "first_name": "Test"}, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(fields.items()))
    secret_key = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient branché sur une base jetable et un BOT_TOKEN de test."""
    db.DB_PATH = tmp_path / "test_mini_app.db"
    db.init_db()
    monkeypatch.setattr(mini_app_module, "BOT_TOKEN", TEST_TOKEN)
    with TestClient(mini_app_module.app) as test_client:
        yield test_client


def _auth(user_id: int = CLIENT_ID, **kwargs) -> dict:
    return {"X-Telegram-Init-Data": _build_init_data(user_id, **kwargs)}


def _register(client, telegram_id: int = CLIENT_ID, **overrides):
    payload = {
        "phone_number": "+243800000001",
        "full_name": "Alice Prestataire",
        "services": ["service_plomberie"],
        "communes": ["Gombe"],
        "language": "fr",
    }
    payload.update(overrides)
    return client.post(
        f"/api/provider/{telegram_id}/register",
        json=payload,
        headers=_auth(telegram_id),
    )


# ── Authentification ────────────────────────────────────────────


def test_valid_init_data_is_accepted(client):
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth())
    assert response.status_code == 200
    assert response.json()["telegram_id"] == CLIENT_ID


def test_request_without_init_data_is_rejected(client):
    response = client.get(f"/api/profile/{CLIENT_ID}")
    assert response.status_code == 401


def test_init_data_signed_with_another_token_is_rejected(client):
    """Le cas qui compte : quelqu'un qui connaît le format mais pas le token."""
    headers = {"X-Telegram-Init-Data": _build_init_data(CLIENT_ID, token="000000:WRONG-TOKEN")}
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=headers)
    assert response.status_code == 401


def test_tampered_payload_invalidates_the_signature(client):
    """On resigne pour OTHER_ID puis on réécrit le user : le hash ne suit pas."""
    init_data = _build_init_data(OTHER_ID)
    forged = init_data.replace(
        urlencode({"user": json.dumps({"id": OTHER_ID, "first_name": "Test"}, separators=(",", ":"))}),
        urlencode({"user": json.dumps({"id": CLIENT_ID, "first_name": "Test"}, separators=(",", ":"))}),
    )
    response = client.get(f"/api/profile/{CLIENT_ID}", headers={"X-Telegram-Init-Data": forged})
    assert response.status_code == 401


def test_init_data_without_hash_is_rejected(client):
    signed = _build_init_data(CLIENT_ID)
    without_hash = "&".join(part for part in signed.split("&") if not part.startswith("hash="))
    response = client.get(f"/api/profile/{CLIENT_ID}", headers={"X-Telegram-Init-Data": without_hash})
    assert response.status_code == 401


def test_expired_session_is_rejected(client):
    """auth_date vieux de plus de 24h : rejeu d'une session légitime mais périmée."""
    stale = int(time.time()) - 86_400 - 60
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth(auth_date=stale))
    assert response.status_code == 401


def test_session_just_within_the_window_is_accepted(client):
    recent = int(time.time()) - 3600
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth(auth_date=recent))
    assert response.status_code == 200


# ── Cloisonnement entre utilisateurs ────────────────────────────


def test_cannot_read_another_users_profile(client):
    """Signature parfaitement valide, mais pour quelqu'un d'autre."""
    response = client.get(f"/api/profile/{OTHER_ID}", headers=_auth(CLIENT_ID))
    assert response.status_code == 403


def test_cannot_register_as_another_user(client):
    response = client.post(
        f"/api/provider/{OTHER_ID}/register",
        json={
            "phone_number": "+243800000009",
            "full_name": "Usurpateur",
            "services": ["service_plomberie"],
            "communes": ["Gombe"],
        },
        headers=_auth(CLIENT_ID),
    )
    assert response.status_code == 403


def test_cannot_change_another_providers_status(client):
    _register(client, OTHER_ID)
    response = client.post(
        f"/api/provider/{OTHER_ID}/status",
        json={"status": "offline"},
        headers=_auth(CLIENT_ID),
    )
    assert response.status_code == 403


# ── Inscription prestataire ─────────────────────────────────────


def test_provider_registration_persists_services_and_communes(client):
    response = _register(client)
    assert response.status_code == 200

    provider = response.json()["provider"]
    assert provider["full_name"] == "Alice Prestataire"
    assert provider["services"] == ["service_plomberie"]
    assert provider["communes"] == ["Gombe"]

    stored = db.get_provider_by_telegram_id(CLIENT_ID)
    assert stored is not None


def test_registration_rejects_unknown_service(client):
    response = _register(client, services=["service_qui_nexiste_pas"])
    assert response.status_code == 400


def test_registration_rejects_unknown_commune(client):
    response = _register(client, communes=["Bruxelles"])
    assert response.status_code == 400


def test_registration_rejects_too_short_name(client):
    response = _register(client, full_name="Al")
    assert response.status_code == 400


def test_registration_rejects_empty_service_list(client):
    response = _register(client, services=[])
    assert response.status_code == 400


# ── Mise à jour du profil prestataire ───────────────────────────


def test_services_update_requires_an_existing_provider(client):
    response = client.post(
        f"/api/provider/{CLIENT_ID}/services",
        json={"services": ["service_plomberie"]},
        headers=_auth(),
    )
    assert response.status_code == 404


def test_services_can_be_updated_after_registration(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/services",
        json={"services": ["service_nettoyage", "service_jardinage"]},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert set(response.json()["provider"]["services"]) == {"service_nettoyage", "service_jardinage"}


def test_status_update_rejects_unknown_value(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/status",
        json={"status": "en_vacances"},
        headers=_auth(),
    )
    assert response.status_code == 400


def test_status_can_be_set_to_offline(client):
    _register(client)
    db.update_provider_status(CLIENT_ID, "available")  # validé par l'admin
    response = client.post(
        f"/api/provider/{CLIENT_ID}/status",
        json={"status": "offline"},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert response.json()["provider"]["status"] == "offline"


def test_unvalidated_provider_cannot_make_itself_available(client):
    """Inscrit via la Mini App : pending_verification jusqu'à validation admin.
    Se remettre "available" (ou "offline" puis "available") l'aurait fait
    entrer dans le matching sans vérification."""
    _register(client)
    for status in ("available", "offline"):
        response = client.post(f"/api/provider/{CLIENT_ID}/status", json={"status": status}, headers=_auth())
        assert response.status_code == 403
    assert db.get_provider_by_telegram_id(CLIENT_ID)["status"] == "pending_verification"


def test_rejected_provider_cannot_make_itself_available(client):
    _register(client)
    db.update_provider_status(CLIENT_ID, "rejected")
    response = client.post(f"/api/provider/{CLIENT_ID}/status", json={"status": "available"}, headers=_auth())
    assert response.status_code == 403
    assert db.get_provider_by_telegram_id(CLIENT_ID)["status"] == "rejected"


# ── Demande de service manquant ─────────────────────────────────


def test_service_request_rejects_too_short_description(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/service-requests",
        json={"service_name": "Soudure", "description": "court"},
        headers=_auth(),
    )
    assert response.status_code == 400


def test_service_request_is_recorded(client):
    _register(client)
    response = client.post(
        f"/api/provider/{CLIENT_ID}/service-requests",
        json={"service_name": "Soudure", "description": "Je fais de la soudure metallique."},
        headers=_auth(),
    )
    assert response.status_code == 200
    assert len(response.json()["service_requests"]) == 1


# ── Routes publiques ────────────────────────────────────────────


def test_health_needs_no_authentication(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# --- Démarrer / finir une mission : décidé par le registre du backend -----------


def _paid_mission_for_provider(live, provider_id: int = CLIENT_ID) -> int:
    """Mission d'un autre client confiée à `provider_id` et payée en escrow."""
    import asyncio

    from telegram_bot import backend_client

    db.create_provider(provider_id, "+243800004242", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id, quote_id = live.accepted_quote(OTHER_ID, provider_id, amount=30.0)
    asyncio.run(backend_client.create_payment_intent(mission_id, quote_id, "+243810000000", "mpesa", OTHER_ID))
    return mission_id


def test_provider_arrives_enters_the_code_and_finishes_through_the_registry(client, live_backend):
    from backend.app import presence

    mission_id = _paid_mission_for_provider(live_backend)

    arrived = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/arrived", headers=_auth())
    assert arrived.status_code == 200
    assert arrived.json()["mission"]["status"] == "confirmed", "« je suis arrivé » seul ne démarre rien"
    assert arrived.json()["presence"] == {"confirmed": False, "client_asked": True}
    assert "code" not in str(arrived.json()), "jamais le code au prestataire"

    wrong = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/presence-code", json={"code": "0000" if presence.presence_code(mission_id) != "0000" else "1111"}, headers=_auth())
    assert wrong.status_code == 409 and wrong.json()["detail"] == {"code": "wrong_presence_code", "attempts_left": 4}

    started = client.post(
        f"/api/provider/{CLIENT_ID}/missions/{mission_id}/presence-code", json={"code": presence.presence_code(mission_id)}, headers=_auth()
    )
    finished = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/finish", headers=_auth())

    assert started.status_code == 200 and started.json()["mission"]["status"] == "in_progress"
    assert finished.status_code == 200 and finished.json()["mission"]["status"] == "awaiting_confirmation"
    assert live_backend.mission(mission_id).status == "awaiting_confirmation"


def test_mission_actions_are_refused_with_a_code(client, live_backend):
    mission_id = _paid_mission_for_provider(live_backend)

    early_finish = client.post(f"/api/provider/{CLIENT_ID}/missions/{mission_id}/finish", headers=_auth())

    assert early_finish.status_code == 409
    assert early_finish.json()["detail"] == {"code": "invalid_state"}


def test_mission_actions_fail_safe_when_the_backend_is_down(client):
    db.create_provider(CLIENT_ID, "+243800004242", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    response = client.post(f"/api/provider/{CLIENT_ID}/missions/1/arrived", headers=_auth())

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "backend_unavailable"}


# ── Wallet : lu dans le registre du backend, jamais un chiffre par défaut ──


def test_profile_shows_the_registry_wallet_of_the_verified_user(client, live_backend):
    live_backend.credit_wallet(CLIENT_ID, 12.5)

    wallet = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()["wallet"]

    assert wallet["wallet_balance_usd"] == 12.5
    assert wallet["wallet_balance_cdf"] == 0.0


def test_profile_lists_the_backend_missions_by_role(client, live_backend):
    ordered = live_backend.new_mission(CLIENT_ID, service="service_plomberie")
    entrusted = _paid_mission_for_provider(live_backend)

    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert [mission["id"] for mission in body["client_missions"]] == [ordered]
    assert [mission["id"] for mission in body["provider_missions"]] == [entrusted]
    assert body["provider_missions"][0]["payment_status"] == "paid_escrow"


def test_profile_missions_are_unknown_when_the_backend_is_down(client):
    body = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth()).json()

    assert body["client_missions"] is None and body["provider_missions"] is None


def test_profile_wallet_is_unknown_when_the_backend_is_down(client):
    response = client.get(f"/api/profile/{CLIENT_ID}", headers=_auth())

    assert response.status_code == 200
    assert response.json()["wallet"] is None
