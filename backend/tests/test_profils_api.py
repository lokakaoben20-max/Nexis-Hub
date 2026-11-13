"""Profils au backend, étape 2 : routes au nom de l'acteur, routes admin
revérifiées par le backend, catalogue, refus d'alerte compté une fois.

Chaque refus est vérifié : pas admin, pas vérifié, suspendu, statut interdit,
service inconnu, action de prestataire depuis WhatsApp, refus rejoué.
"""

import importlib
import itertools

import pytest
from fastapi.testclient import TestClient

from backend.app import admins
from backend.tests import profils_de_test

TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-0001"
WHATSAPP_KEY = "test-whatsapp-service-key-not-a-secret-0002"
BSUID = "CD.13491208655302741918"
ADMIN = 900
CLIENT = 42
PROVIDER = 7
_KEYS = itertools.count(1)


@pytest.fixture
def backend(backend_db_url, monkeypatch):
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    with database.SessionLocal() as db:
        profils_de_test.admin(db, ADMIN)
    main.database = database
    return main


@pytest.fixture
def api(backend):
    with TestClient(backend.app) as test_client:
        yield test_client


def tg(telegram_id):
    return {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def wa(bsuid=BSUID):
    return {"X-API-Key": WHATSAPP_KEY, "X-Actor-Channel": "whatsapp", "X-Actor-Id": bsuid}


def code(response):
    return response.json()["detail"]["code"]


def register(api, telegram_id=PROVIDER, services=("service_nettoyage",), communes=("Gombe",), **fields):
    payload = {
        "full_name": "Jean Mukendi",
        "phone_number": "+243810000007",
        "services": list(services),
        "communes": list(communes),
        **fields,
    }
    return api.put("/api/me/provider-profile", json=payload, headers=tg(telegram_id))


def account_of(api, telegram_id):
    return api.get("/api/me/profile", headers=tg(telegram_id)).json()["account_id"]


def verified_provider(api, telegram_id=PROVIDER, **fields):
    assert register(api, telegram_id, **fields).status_code == 200
    account_id = account_of(api, telegram_id)
    assert api.post(f"/api/admin/providers/{account_id}/verify", headers=tg(ADMIN)).status_code == 200
    assert api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=tg(telegram_id)).status_code == 200
    return account_id


def mission(api, client=CLIENT, alert=(PROVIDER,)):
    api.put("/api/me/client-profile", json={"first_name": "Client"}, headers=tg(client))
    response = api.post(
        "/api/bot/missions",
        json={
            "creation_key": f"demande-{next(_KEYS)}",
            "service": "service_nettoyage",
            "commune": "Gombe",
            "alert_provider_telegram_ids": list(alert),
            "destination": {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"},
        },
        headers=tg(client),
    )
    assert response.status_code == 200, response.json()
    return response.json()["mission"]["mission_id"]


# --- Catalogue ----------------------------------------------------------------


def test_the_catalogue_lists_services_in_three_languages_and_the_served_communes(api):
    for headers in (tg(CLIENT), wa()):
        body = api.get("/api/services", headers=headers).json()
        plomberie = next(service for service in body["services"] if service["key"] == "service_plomberie")
        assert plomberie["names"] == {"fr": "Plomberie", "ln": "Plomberie", "en": "Plumbing"}
        assert (plomberie["module"], plomberie["requires_inspection"], plomberie["visit_fee_usd"]) == ("B", True, "5.00")
        assert [service["key"] for service in body["services"]][0] == "service_plomberie"
        assert body["communes"][0] == "Gombe" and body["communes"][-1] == "Autre commune"


def test_the_catalogue_needs_a_service_key(api):
    assert api.get("/api/services").status_code == 401


# --- Profil de l'acteur ---------------------------------------------------------


def test_an_unknown_person_is_a_guest_and_nothing_is_created(api):
    body = api.get("/api/me/profile", headers=tg(555)).json()
    assert (body["profile_type"], body["account_id"], body["client"], body["provider"]) == ("guest", None, None, None)
    assert api.get("/api/me/profile", headers=tg(555)).json()["account_id"] is None


def test_a_client_registers_renames_and_changes_language_as_himself(api):
    saved = api.put("/api/me/client-profile", json={"first_name": "Marie", "language": "ln"}, headers=tg(CLIENT))
    assert saved.status_code == 200
    assert (saved.json()["profile_type"], saved.json()["client"]["first_name"], saved.json()["language"]) == ("client", "Marie", "ln")

    assert api.patch("/api/me/name", json={"first_name": "Marie-Claire"}, headers=tg(CLIENT)).json()["client"]["first_name"] == "Marie-Claire"
    assert api.patch("/api/me/language", json={"language": "en"}, headers=tg(CLIENT)).json()["language"] == "en"
    # Un autre acteur ne voit que lui-même.
    assert api.get("/api/me/profile", headers=tg(43)).json()["profile_type"] == "guest"


def test_client_profile_refusals(api):
    assert code(api.put("/api/me/client-profile", json={"first_name": "Marie", "language": "de"}, headers=tg(CLIENT))) == "invalid_language"
    assert api.get("/api/me/profile", headers=tg(CLIENT)).json()["client"] is None, "refus : rien d'écrit"
    assert code(api.patch("/api/me/language", json={"language": "fr"}, headers=tg(44))) == "account_not_found"
    assert api.put("/api/me/client-profile", json={"first_name": ""}, headers=tg(CLIENT)).status_code == 422


def test_whatsapp_reads_and_edits_its_own_client_profile_only(api):
    assert api.post("/api/whatsapp/client", json={"display_name": "Marie", "language": "fr"}, headers=wa()).status_code == 200
    assert api.get("/api/me/profile", headers=wa()).json()["client"]["first_name"] == "Marie"
    assert api.patch("/api/me/name", json={"first_name": "Mama Marie"}, headers=wa()).json()["client"]["first_name"] == "Mama Marie"
    assert api.patch("/api/me/language", json={"language": "ln"}, headers=wa()).json()["language"] == "ln"
    # Inscription client par la route Telegram : fermée à WhatsApp.
    assert code(api.put("/api/me/client-profile", json={"first_name": "X"}, headers=wa())) == "channel_forbidden"


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("put", "/api/me/provider-profile", {"full_name": "X", "phone_number": "1", "services": [], "communes": []}),
        ("put", "/api/me/provider-profile/services", {"services": ["service_nettoyage"]}),
        ("put", "/api/me/provider-profile/communes", {"communes": ["Gombe"]}),
        ("patch", "/api/me/provider-profile/status", {"status": "available"}),
        ("post", "/api/bot/missions/1/decline", None),
    ],
)
def test_provider_actions_are_refused_from_whatsapp(api, method, path, payload):
    response = getattr(api, method)(path, headers=wa(), **({"json": payload} if payload is not None else {}))
    assert (response.status_code, code(response)) == (403, "provider_channel_forbidden")


# --- Prestataire ------------------------------------------------------------------


def test_a_new_provider_waits_for_verification_and_cannot_make_himself_available(api):
    body = register(api).json()
    assert (body["profile_type"], body["provider"]["status"], body["provider"]["is_verified"]) == ("provider", "pending_verification", False)
    refused = api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=tg(PROVIDER))
    assert (refused.status_code, code(refused)) == (409, "provider_not_verified")


def test_a_provider_may_only_choose_available_or_offline(api):
    verified_provider(api)
    for status in ("paused", "rejected", "pending_verification", "verified"):
        refused = api.patch("/api/me/provider-profile/status", json={"status": status}, headers=tg(PROVIDER))
        assert code(refused) == "status_not_allowed", status
    offline = api.patch("/api/me/provider-profile/status", json={"status": "offline"}, headers=tg(PROVIDER))
    assert offline.json()["provider"]["status"] == "offline"


def test_a_suspended_provider_cannot_become_available(api):
    account_id = verified_provider(api)
    api.patch("/api/me/provider-profile/status", json={"status": "offline"}, headers=tg(PROVIDER))
    assert api.post(f"/api/admin/providers/{account_id}/suspend", headers=tg(ADMIN)).status_code == 200
    refused = api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=tg(PROVIDER))
    assert code(refused) == "provider_suspended"


def test_registration_refuses_services_and_communes_outside_the_catalogue(api):
    assert code(register(api, services=["service_peinture"])) == "unknown_service"
    assert code(register(api, communes=["Kintambo"])) == "unknown_commune"
    assert code(register(api, services=[])) == "services_required"
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"] is None, "refus : rien d'écrit"


def test_a_provider_changes_his_services_and_communes(api):
    register(api)
    services = api.put("/api/me/provider-profile/services", json={"services": ["service_plomberie"]}, headers=tg(PROVIDER))
    assert (services.json()["provider"]["services"], services.json()["provider"]["module"]) == (["service_plomberie"], "B")
    communes = api.put("/api/me/provider-profile/communes", json={"communes": ["Lemba", "Gombe"]}, headers=tg(PROVIDER))
    assert sorted(communes.json()["provider"]["communes"]) == ["Gombe", "Lemba"]
    assert code(api.put("/api/me/provider-profile/services", json={"services": ["service_x"]}, headers=tg(PROVIDER))) == "unknown_service"
    assert code(api.put("/api/me/provider-profile/communes", json={"communes": ["Gombe"]}, headers=tg(8))) == "provider_not_found"


def test_re_registering_never_changes_a_verified_status(api):
    verified_provider(api)
    again = register(api, services=["service_plomberie"])
    assert (again.json()["provider"]["status"], again.json()["provider"]["services"]) == ("available", ["service_plomberie"])


# --- Admin ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/admin/providers"),
        ("post", "/api/admin/providers/1/verify"),
        ("post", "/api/admin/providers/1/reject"),
        ("post", "/api/admin/providers/1/suspend"),
        ("post", "/api/admin/providers/1/unsuspend"),
        ("get", "/api/admin/service-requests"),
    ],
)
def test_admin_routes_refuse_anyone_but_the_configured_admin(api, method, path):
    register(api)
    for headers in (tg(PROVIDER), tg(CLIENT)):
        refused = getattr(api, method)(path, headers=headers)
        assert (refused.status_code, code(refused)) == (403, "not_admin")
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]["status"] == "pending_verification"


def test_without_a_configured_admin_nobody_is_admin(api, backend):
    register(api)
    with backend.database.SessionLocal() as db:
        admins.revoke(db, ADMIN, "Fin du test")
    assert code(api.get("/api/admin/providers", headers=tg(ADMIN))) == "not_admin"


def test_the_admin_lists_verifies_rejects_and_suspends(api):
    register(api)
    register(api, 8)
    pending = api.get("/api/admin/providers", params={"status": "pending_verification"}, headers=tg(ADMIN)).json()["providers"]
    assert [provider["telegram_id"] for provider in pending] == [PROVIDER, 8]
    first, second = (provider["account_id"] for provider in pending)

    verified = api.post(f"/api/admin/providers/{first}/verify", headers=tg(ADMIN)).json()["provider"]
    assert (verified["status"], verified["is_verified"]) == ("available", True)
    assert api.post(f"/api/admin/providers/{first}/verify", headers=tg(ADMIN)).json()["provider"]["status"] == "available", "idempotent"

    rejected = api.post(f"/api/admin/providers/{second}/reject", headers=tg(ADMIN)).json()["provider"]
    assert rejected["status"] == "rejected"
    assert code(api.post(f"/api/admin/providers/{second}/verify", headers=tg(ADMIN))) == "provider_not_pending"

    suspended = api.post(f"/api/admin/providers/{first}/suspend", headers=tg(ADMIN)).json()["provider"]
    assert (suspended["is_suspended"], suspended["status"]) == (True, "available"), "la suspension ne touche pas au statut"
    assert api.post(f"/api/admin/providers/{first}/unsuspend", headers=tg(ADMIN)).json()["provider"]["is_suspended"] is False

    assert code(api.post("/api/admin/providers/9999/verify", headers=tg(ADMIN))) == "provider_not_found"
    assert code(api.get("/api/admin/providers", params={"status": "nope"}, headers=tg(ADMIN))) == "invalid_status"


def test_the_admin_decides_a_service_request_once(api):
    register(api)
    created = api.post("/api/bot/service-requests", json={"service_name": "Peinture", "description": "Murs"}, headers=tg(PROVIDER))
    assert created.status_code == 200, created.json()
    request_id = created.json()["service_request"]["id"]
    assert code(api.patch(f"/api/admin/service-requests/{request_id}", json={"status": "accepted"}, headers=tg(PROVIDER))) == "not_admin"

    listed = api.get("/api/admin/service-requests", headers=tg(ADMIN)).json()["service_requests"]
    assert [item["id"] for item in listed] == [request_id]
    decided = api.patch(f"/api/admin/service-requests/{request_id}", json={"status": "accepted"}, headers=tg(ADMIN))
    assert decided.json()["service_request"]["status"] == "accepted"
    again = api.patch(f"/api/admin/service-requests/{request_id}", json={"status": "rejected"}, headers=tg(ADMIN))
    assert (again.status_code, code(again)) == (409, "already_reviewed")
    assert code(api.patch(f"/api/admin/service-requests/{request_id}", json={"status": "maybe"}, headers=tg(ADMIN))) == "invalid_status"
    assert code(api.patch("/api/admin/service-requests/9999", json={"status": "accepted"}, headers=tg(ADMIN))) == "service_request_not_found"


# --- Refus d'alerte -----------------------------------------------------------------


def decline(api, mission_id, telegram_id=PROVIDER):
    return api.post(f"/api/bot/missions/{mission_id}/decline", headers=tg(telegram_id))


def test_a_decline_counts_once_per_alert_and_the_third_in_a_row_pauses(api):
    verified_provider(api)
    missions = [mission(api) for _ in range(3)]

    first = decline(api, missions[0]).json()
    assert (first["counted"], first["provider"]["consecutive_ignored"], first["paused_now"]) == (True, 1, False)
    replay = decline(api, missions[0]).json()
    assert (replay["counted"], replay["provider"]["consecutive_ignored"]) == (False, 1), "un appui rejoué ne recompte pas"

    decline(api, missions[1])
    third = decline(api, missions[2]).json()
    assert (third["provider"]["consecutive_ignored"], third["provider"]["status"], third["paused_now"]) == (3, "paused", True)


def test_a_quote_resets_the_declines_in_a_row(api):
    verified_provider(api)
    declined, quoted = mission(api), mission(api)
    decline(api, declined)
    decline(api, mission(api))
    response = api.post(
        "/api/bot/quotes",
        json={"mission_id": quoted, "amount": 20, "currency": "USD", "delay_hours": 2},
        headers=tg(PROVIDER),
    )
    assert response.status_code == 200, response.json()
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]["consecutive_ignored"] == 0


def test_decline_refusals(api):
    verified_provider(api)
    verified_provider(api, 8)
    mission_id = mission(api)
    assert (decline(api, mission_id, 8).status_code, code(decline(api, mission_id, 8))) == (403, "provider_not_alerted")
    assert code(decline(api, 9999)) == "provider_not_alerted"
    api.post("/api/bot/quotes", json={"mission_id": mission_id, "amount": 20, "currency": "USD", "delay_hours": 2}, headers=tg(PROVIDER))
    assert code(decline(api, mission_id)) == "already_quoted"
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]["consecutive_ignored"] == 0
