"""Profils au backend, étape 2 : routes au nom de l'acteur, routes admin
revérifiées par le backend, catalogue, refus d'alerte compté une fois.

Chaque refus est vérifié : pas admin, pas vérifié, suspendu, statut interdit,
service inconnu, action de prestataire depuis WhatsApp, refus rejoué.
"""

import importlib
import itertools

import uuid

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


def wa_write(bsuid=BSUID):
    """En-têtes d'une écriture WhatsApp : chaque message a sa clé d'idempotence."""
    return {**wa(bsuid), "Idempotency-Key": f"wamid.{uuid.uuid4().hex}"}


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


def mission(api, client=CLIENT):
    """Mission de nettoyage à Gombe : le backend prévient les prestataires
    vérifiés et disponibles qui font ce travail dans cette commune."""
    api.put("/api/me/client-profile", json={"first_name": "Client"}, headers=tg(client))
    response = api.post(
        "/api/bot/missions",
        json={
            "creation_key": f"demande-{next(_KEYS)}",
            "service": "service_nettoyage",
            "commune": "Gombe",
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
    assert api.post("/api/whatsapp/client", json={"display_name": "Marie", "language": "fr"}, headers=wa_write()).status_code == 200
    assert api.get("/api/me/profile", headers=wa()).json()["client"]["first_name"] == "Marie"
    assert api.patch("/api/me/name", json={"first_name": "Mama Marie"}, headers=wa_write()).json()["client"]["first_name"] == "Mama Marie"
    assert api.patch("/api/me/language", json={"language": "ln"}, headers=wa_write()).json()["language"] == "ln"
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
    again = register(api, communes=["Lemba"])
    assert (again.json()["provider"]["status"], again.json()["provider"]["communes"]) == ("available", ["Lemba"])
    # Un service de plus passe par une demande à l'équipe, jamais directement.
    added = register(api, services=["service_nettoyage", "service_plomberie"])
    assert (added.status_code, code(added)) == (400, "service_needs_review")


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
        ("get", "/api/admin/service-additions"),
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
    created = api.post("/api/bot/service-requests", json={"service_name": "Peinture", "description": "Murs et plafonds"}, headers=tg(PROVIDER))
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
    verified_provider(api, 8, communes=("Lemba",))  # pas prévenu : autre commune
    mission_id = mission(api)
    assert (decline(api, mission_id, 8).status_code, code(decline(api, mission_id, 8))) == (403, "provider_not_alerted")
    assert code(decline(api, 9999)) == "provider_not_alerted"
    api.post("/api/bot/quotes", json={"mission_id": mission_id, "amount": 20, "currency": "USD", "delay_hours": 2}, headers=tg(PROVIDER))
    assert code(decline(api, mission_id)) == "already_quoted"
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]["consecutive_ignored"] == 0


# --- Besoins des clients hors catalogue (décision du 2026-11-15) --------------


def test_other_service_is_no_longer_a_mission_for_clients(api):
    assert api.get("/api/services", headers=tg(CLIENT)).json()["client_excluded_services"] == ["service_autre"]
    payload = {
        "creation_key": "k-autre",
        "service": "service_autre",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Poser du carrelage",
        "urgent": False,
        "media": [],
        "destination": {"latitude": -4.3, "longitude": 15.3, "landmark": "Près du marché central"},
    }
    refused = api.post("/api/bot/missions", json=payload, headers=tg(CLIENT))
    assert (refused.status_code, code(refused)) == (400, "service_not_requestable")


def test_a_client_sends_a_need_and_one_admin_answers_it_once(api):
    sent = api.post("/api/me/client-requests", json={"description": "  Poser du carrelage   dans la cuisine "}, headers=tg(CLIENT))
    assert sent.status_code == 200
    request = sent.json()["client_request"]
    assert (request["description"], request["status"]) == ("Poser du carrelage dans la cuisine", "pending")
    assert "client_telegram_id" not in request

    assert code(api.post("/api/me/client-requests", json={"description": "court"}, headers=tg(CLIENT))) == "invalid_description"
    assert api.get("/api/admin/client-requests", headers=tg(CLIENT)).status_code == 403
    assert api.get("/api/admin/stats", headers=tg(ADMIN)).json()["stats"]["pending_client_requests"] == 1

    listed = api.get("/api/admin/client-requests", headers=tg(ADMIN)).json()["client_requests"]
    assert [(item["id"], item["client_telegram_id"]) for item in listed] == [(request["id"], CLIENT)]

    decide = f"/api/admin/client-requests/{request['id']}/decision"
    assert code(api.post(decide, json={"status": "pending"}, headers=tg(ADMIN))) == "invalid_status"
    assert api.post(decide, json={"status": "accepted"}, headers=tg(CLIENT)).status_code == 403
    accepted = api.post(decide, json={"status": "accepted", "admin_note": "On cherche"}, headers=tg(ADMIN))
    assert (accepted.json()["client_request"]["status"], accepted.json()["client_request"]["client_language"]) == ("accepted", "fr")
    again = api.post(decide, json={"status": "rejected"}, headers=tg(ADMIN))
    assert (again.status_code, code(again)) == (409, "already_reviewed")
    assert code(api.post("/api/admin/client-requests/999/decision", json={"status": "rejected"}, headers=tg(ADMIN))) == "client_request_not_found"

    mine = api.get("/api/me/client-requests", headers=tg(CLIENT)).json()["client_requests"]
    assert [(item["status"], item["admin_note"]) for item in mine] == [("accepted", "On cherche")]
    assert api.get("/api/admin/client-requests", headers=tg(ADMIN)).json()["client_requests"] == []


def test_a_client_cannot_pile_up_unanswered_needs(api, backend):
    for index in range(backend.crud.MAX_PENDING_CLIENT_REQUESTS):
        assert api.post("/api/me/client-requests", json={"description": f"Besoin numéro {index}"}, headers=tg(CLIENT)).status_code == 200
    refused = api.post("/api/me/client-requests", json={"description": "Un besoin de trop"}, headers=tg(CLIENT))
    assert (refused.status_code, code(refused)) == (409, "too_many_pending_requests")


# --- Ajout d'un service : demande approuvée par l'équipe (2026-11-15) -------


JPEG = b"\xff\xd8\xff\xe0" + b"realisation" * 20


@pytest.fixture(autouse=True)
def _files_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("FILES_DIR", str(tmp_path / "fichiers"))
    monkeypatch.delenv("FILES_ENCRYPTION_KEY", raising=False)


def upload(api, data=JPEG, telegram_id=PROVIDER):
    return api.post(
        "/api/me/files/service-photos", content=data, headers={**tg(telegram_id), "Content-Type": "image/jpeg"}
    )


def ask(api, service="service_coiffure", telegram_id=PROVIDER, **fields):
    return api.post(
        "/api/me/provider-profile/service-additions", json={"service_key": service, **fields}, headers=tg(telegram_id)
    )


def test_a_verified_provider_asks_for_a_service_and_the_admin_approves_it_once(api):
    verified_provider(api)
    direct = api.put("/api/me/provider-profile/services", json={"services": ["service_nettoyage", "service_coiffure"]}, headers=tg(PROVIDER))
    assert (direct.status_code, code(direct)) == (400, "service_needs_review")

    photos = [upload(api).json()["file"]["id"] for _ in range(2)]
    asked = ask(api, description="Coiffeur depuis 5 ans", photo_ids=photos)
    assert asked.status_code == 200, asked.json()
    addition = asked.json()["service_addition"]
    assert (addition["status"], addition["photo_count"]) == ("pending", 2)
    assert "photo_ids" not in addition, "les photos ne reviennent qu'à l'admin"
    me = api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]
    assert (me["services"], me["pending_services"]) == (["service_nettoyage"], ["service_coiffure"])
    assert api.get("/api/admin/stats", headers=tg(ADMIN)).json()["stats"]["pending_service_additions"] == 1

    listed = api.get("/api/admin/service-additions", headers=tg(ADMIN)).json()["service_additions"]
    assert [(item["id"], item["provider_telegram_id"], sorted(item["photo_ids"])) for item in listed] == [
        (addition["id"], PROVIDER, sorted(photos))
    ]
    seen = api.get(f"/api/admin/files/{photos[0]}", headers=tg(ADMIN))
    assert (seen.status_code, seen.content, seen.headers["content-type"]) == (200, JPEG, "image/jpeg")
    assert seen.headers["cache-control"] == "no-store"
    for intruder in (PROVIDER, CLIENT):
        blocked = api.get(f"/api/admin/files/{photos[0]}", headers=tg(intruder))
        assert (blocked.status_code, code(blocked)) == (403, "not_admin")
    assert (listed[0]["provider_language"], listed[0]["provider_services"], listed[0]["previously_rejected"]) == ("fr", ["service_nettoyage"], False)

    url = f"/api/admin/service-additions/{addition['id']}/decision"
    refused = api.post(url, json={"decision": "approve"}, headers=tg(PROVIDER))
    assert (refused.status_code, code(refused)) == (403, "not_admin")
    approved = api.post(url, json={"decision": "approve"}, headers=tg(ADMIN))
    assert (approved.json()["decided_now"], approved.json()["service_addition"]["status"]) == (True, "approved")
    again = api.post(url, json={"decision": "approve"}, headers=tg(ADMIN))
    assert again.json()["decided_now"] is False, "double clic : le prestataire n'est pas prévenu deux fois"
    other = api.post(url, json={"decision": "reject"}, headers=tg(ADMIN))
    assert (other.status_code, code(other)) == (409, "already_decided")
    me = api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]
    assert (sorted(me["services"]), me["pending_services"]) == (["service_coiffure", "service_nettoyage"], [])
    assert api.get("/api/admin/service-additions", headers=tg(ADMIN)).json()["service_additions"] == []


def test_a_rejected_request_is_shown_to_the_admin_when_asked_again(api):
    verified_provider(api)
    first = ask(api).json()["service_addition"]
    api.post(f"/api/admin/service-additions/{first['id']}/decision", json={"decision": "reject", "admin_note": "Aucune photo"}, headers=tg(ADMIN))
    mine = api.get("/api/me/provider-profile/service-additions", headers=tg(PROVIDER)).json()["service_additions"]
    assert [(item["status"], item["admin_note"]) for item in mine] == [("rejected", "Aucune photo")]
    assert ask(api).status_code == 200
    listed = api.get("/api/admin/service-additions", headers=tg(ADMIN)).json()["service_additions"]
    assert (listed[0]["previously_rejected"], listed[0]["previous_rejection_note"]) == (True, "Aucune photo")


def test_a_provider_cancels_his_request_and_never_someone_else_s(api):
    verified_provider(api)
    verified_provider(api, 8)
    addition = ask(api).json()["service_addition"]
    url = f"/api/me/provider-profile/service-additions/{addition['id']}/cancel"
    stranger = api.post(url, headers=tg(8))
    assert (stranger.status_code, code(stranger)) == (404, "service_addition_not_found")
    assert api.post(url, headers=tg(PROVIDER)).json()["service_addition"]["status"] == "cancelled"
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"]["pending_services"] == []


def test_service_addition_refusals(api):
    register(api)
    assert code(ask(api)) == "provider_not_verified"
    verified_provider(api, 8, services=("service_nettoyage", "service_plomberie"))
    assert ask(api, telegram_id=8).status_code == 200
    assert code(ask(api, telegram_id=8)) == "service_addition_pending"
    assert code(ask(api, "service_jardinage", telegram_id=8)) == "too_many_services"
    assert code(ask(api, "service_nettoyage", telegram_id=8)) == "service_already_offered"
    assert code(ask(api, telegram_id=9)) == "provider_not_found"
    whatsapp = api.post("/api/me/provider-profile/service-additions", json={"service_key": "service_coiffure"}, headers=wa_write())
    assert whatsapp.status_code == 403


def test_photo_upload_refusals(api):
    verified_provider(api)
    assert code(upload(api, b"%PDF-1.7")) == "unsupported_file_type"
    big = upload(api, b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024))
    assert (big.status_code, code(big)) == (413, "file_too_large")
    assert code(upload(api, telegram_id=CLIENT)) == "provider_not_found"
    whatsapp = api.post("/api/me/files/service-photos", content=JPEG, headers={**wa_write(), "Content-Type": "image/jpeg"})
    assert whatsapp.status_code == 403
    missing = api.get("/api/admin/files/" + "0" * 32, headers=tg(ADMIN))
    assert (missing.status_code, code(missing)) == (404, "file_not_found")
    # La photo d'un autre ne se joint pas à sa demande.
    verified_provider(api, 8)
    foreign = upload(api, telegram_id=8).json()["file"]["id"]
    assert code(ask(api, photo_ids=[foreign])) == "invalid_photos"
