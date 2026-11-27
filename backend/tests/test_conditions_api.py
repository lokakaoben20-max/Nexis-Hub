"""La case des conditions d'utilisation, vue des canaux (routes du backend).

Inscription client, prestataire, bascule client -> prestataire et inscription
WhatsApp : refusées sans la case, enregistrées avec, dans la même transaction
que le profil. Nouvelle version en vigueur : nouvelles actions refusées
jusqu'à la nouvelle case ; ce qui est engagé et l'argent restent accessibles.
Chaque route déclare ce qu'elle exige, et la liste des routes qui exigent la
case est fixée ici.
"""

import importlib
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app import conditions
from backend.tests import profils_de_test

pytestmark = pytest.mark.conditions_reelles

TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-0001"
WHATSAPP_KEY = "test-whatsapp-service-key-not-a-secret-0002"
BSUID = "CD.13491208655302741918"
ADMIN = 900
CLIENT = 42
PROVIDER = 7


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
        profils_de_test.ensure_catalogue(db)
        profils_de_test.admin(db, ADMIN)
        db.commit()
    main.database = database
    return main


@pytest.fixture
def api(backend):
    with TestClient(backend.app) as test_client:
        yield test_client


def publish(backend, key, version):
    with backend.SessionLocal() as db:
        conditions.publish_version(db, key, version, f"Texte de {key}, version {version}.")
        db.commit()


@pytest.fixture
def published(backend):
    publish(backend, conditions.CGU, "v1")
    publish(backend, conditions.PROVIDER_TERMS, "v1")


def tg(telegram_id):
    return {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def wa(bsuid=BSUID):
    return {"X-API-Key": WHATSAPP_KEY, "X-Actor-Channel": "whatsapp", "X-Actor-Id": bsuid}


def wa_write(bsuid=BSUID, key=None):
    return {**wa(bsuid), "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}"}


def code(response):
    return response.json()["detail"]["code"]


def terms(surface="telegram_bot", *pairs):
    pairs = pairs or (("cgu", "v1"),)
    return {"surface": surface, "documents": [{"document_key": key, "version": version} for key, version in pairs]}


PROVIDER_TERMS_V1 = (("cgu", "v1"), ("conditions_prestataires", "v1"))


def client_signup(api, telegram_id=CLIENT, **fields):
    return api.put("/api/me/client-profile", json={"first_name": "Marie", **fields}, headers=tg(telegram_id))


def provider_signup(api, telegram_id=PROVIDER, **fields):
    payload = {
        "full_name": "Jean Mukendi",
        "phone_number": "+243810000007",
        "services": ["service_nettoyage"],
        "communes": ["Gombe"],
        **fields,
    }
    return api.put("/api/me/provider-profile", json=payload, headers=tg(telegram_id))


def acceptances(backend):
    with backend.SessionLocal() as db:
        rows = db.scalars(select(conditions.LegalAcceptance).order_by(conditions.LegalAcceptance.id)).all()
        return [(row.account_id, row.role, row.surface, row.language) for row in rows]


def create_mission(api, telegram_id=CLIENT):
    return api.post(
        "/api/bot/missions",
        json={
            "creation_key": f"demande-{uuid.uuid4().hex[:12]}",
            "service": "service_nettoyage",
            "commune": "Gombe",
            "destination": {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"},
        },
        headers=tg(telegram_id),
    )


# --- Chaque route déclare ce qu'elle exige ------------------------------------------

GATED_ROUTES = {
    # Nouvelles actions de client.
    ("POST", "/api/bot/missions"): "client",
    ("POST", "/api/bot/quotes/{quote_id}/accept"): "client",
    ("POST", "/api/bot/missions/{mission_id}/fund"): "client",
    ("POST", "/api/bot/missions/{mission_id}/payment-intents"): "client",
    ("POST", "/api/me/client-requests"): "client",
    # Nouvelles actions de prestataire.
    ("POST", "/api/bot/quotes"): "provider",
    ("POST", "/api/bot/service-requests"): "provider",
    ("PUT", "/api/me/provider-profile/services"): "provider",
    ("POST", "/api/me/files/service-photos"): "provider",
    ("POST", "/api/me/provider-profile/service-additions"): "provider",
    ("PUT", "/api/me/provider-profile/communes"): "provider",
}


def test_every_route_declares_what_it_requires_and_exactly_these_require_the_box(backend):
    declared = {}
    for route in backend.router.routes:
        terms_policy = backend.route_terms(route.endpoint)
        assert terms_policy is not None, route.path
        for method in route.methods:
            if terms_policy != "exempt":
                declared[(method, route.path)] = terms_policy
    assert declared == GATED_ROUTES


def test_a_route_without_a_declaration_stops_the_backend(backend, monkeypatch):
    route = next(route for route in backend.router.routes if route.path == "/api/me/wallet")
    monkeypatch.delattr(route.endpoint, "__nexis_terms__")
    with pytest.raises(RuntimeError, match="ni @needs_terms ni @terms_exempt"):
        backend.check_route_policies()


# --- Inscription ------------------------------------------------------------------


def test_nothing_published_means_no_signup(api, backend):
    response = client_signup(api)
    assert (response.status_code, code(response)) == (503, "terms_unavailable")
    assert api.get("/api/me/profile", headers=tg(CLIENT)).json()["profile_type"] == "guest"


def test_a_client_signup_needs_the_box_and_is_recorded_with_it(api, backend, published):
    refused = client_signup(api)
    assert (refused.status_code, code(refused)) == (409, "terms_not_accepted")
    assert [item["document_key"] for item in refused.json()["detail"]["missing"]] == ["cgu"]
    # Rien n'est créé sans la case : ni compte, ni profil.
    assert api.get("/api/me/profile", headers=tg(CLIENT)).json()["account_id"] is None

    saved = client_signup(api, language="ln", terms=terms())
    assert saved.status_code == 200, saved.json()
    account_id = saved.json()["account_id"]
    assert acceptances(backend) == [(account_id, "client", "telegram_bot", "ln")]
    assert api.get("/api/me/terms", headers=tg(CLIENT)).json()["complete"] is True
    # Mettre à jour son profil plus tard ne redemande rien.
    assert client_signup(api).status_code == 200


def test_a_signup_with_an_outdated_version_is_refused(api, backend, published):
    publish(backend, conditions.CGU, "v2")
    response = client_signup(api, terms=terms())
    assert (response.status_code, code(response)) == (409, "terms_version_outdated")
    assert acceptances(backend) == []


def test_the_surface_must_belong_to_the_channel(api, published):
    response = client_signup(api, terms=terms("whatsapp"))
    assert (response.status_code, code(response)) == (422, "invalid_surface")


def test_a_new_provider_ticks_both_documents(api, backend, published):
    only_cgu = provider_signup(api, terms=terms("mini_app"))
    assert (only_cgu.status_code, code(only_cgu)) == (409, "terms_not_accepted")
    assert [item["document_key"] for item in only_cgu.json()["detail"]["missing"]] == ["conditions_prestataires"]
    assert api.get("/api/me/profile", headers=tg(PROVIDER)).json()["provider"] is None
    assert acceptances(backend) == []

    saved = provider_signup(api, terms=terms("mini_app", *PROVIDER_TERMS_V1))
    assert saved.status_code == 200, saved.json()
    assert saved.json()["provider"]["status"] == "pending_verification"
    assert [row[1:3] for row in acceptances(backend)] == [("provider", "mini_app"), ("provider", "mini_app")]


def test_a_client_who_becomes_a_provider_ticks_the_provider_terms(api, backend, published):
    assert client_signup(api, terms=terms()).status_code == 200
    refused = provider_signup(api, telegram_id=CLIENT)
    assert (refused.status_code, code(refused)) == (409, "terms_not_accepted")
    assert [item["document_key"] for item in refused.json()["detail"]["missing"]] == ["conditions_prestataires"]
    assert api.get("/api/me/profile", headers=tg(CLIENT)).json()["provider"] is None

    switched = provider_signup(api, telegram_id=CLIENT, terms=terms("telegram_bot", ("conditions_prestataires", "v1")))
    assert switched.status_code == 200, switched.json()
    assert [row[1] for row in acceptances(backend)] == ["client", "provider"]


def test_a_whatsapp_signup_needs_the_box(api, backend, published):
    payload = {"display_name": "Marie", "language": "fr"}
    refused = api.post("/api/whatsapp/client", json=payload, headers=wa_write())
    assert (refused.status_code, code(refused)) == (409, "terms_not_accepted")
    assert api.get("/api/me/profile", headers=wa()).json()["account_id"] is None

    wrong = api.post("/api/whatsapp/client", json={**payload, "terms": terms("telegram_bot")}, headers=wa_write())
    assert (wrong.status_code, code(wrong)) == (422, "invalid_surface")

    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post("/api/whatsapp/client", json={**payload, "terms": terms("whatsapp")}, headers=wa_write(key=key))
    replay = api.post("/api/whatsapp/client", json={**payload, "terms": terms("whatsapp")}, headers=wa_write(key=key))
    assert first.status_code == replay.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert [row[1:] for row in acceptances(backend)] == [("client", "whatsapp", "fr")]


# --- Nouvelle version en vigueur ---------------------------------------------------


def test_new_actions_wait_for_the_new_box_but_money_and_reads_stay_open(api, backend, published):
    assert client_signup(api, terms=terms()).status_code == 200
    assert create_mission(api).status_code == 200

    publish(backend, conditions.CGU, "v2")
    refused = create_mission(api)
    assert (refused.status_code, code(refused)) == (409, "terms_not_accepted")
    assert refused.json()["detail"]["missing"][0]["version"] == "v2"
    # Lire, voir son argent, demander un retrait : toujours possible.
    assert api.get("/api/me/wallet", headers=tg(CLIENT)).status_code == 200
    assert api.get("/api/me/missions", headers=tg(CLIENT)).status_code == 200
    payout = api.post(
        "/api/bot/payouts",
        json={"amount": 5, "currency": "USD", "destination_id": 1},
        headers=tg(CLIENT),
    )
    assert code(payout) != "terms_not_accepted"

    status = api.get("/api/me/terms", headers=tg(CLIENT)).json()
    assert (status["complete"], status["role"]) == (False, "client")
    accepted = api.post("/api/me/terms", json={"role": "client", **terms("telegram_bot", ("cgu", "v2"))}, headers=tg(CLIENT))
    assert accepted.status_code == 200, accepted.json()
    assert accepted.json()["complete"] is True
    assert create_mission(api).status_code == 200


def test_an_account_from_before_the_rule_must_tick_before_acting(api, backend, published):
    with backend.SessionLocal() as db:
        profils_de_test.client(db, CLIENT)
    status = api.get("/api/me/terms", headers=tg(CLIENT)).json()
    assert [item["document_key"] for item in status["missing"]] == ["cgu"]
    assert code(create_mission(api)) == "terms_not_accepted"


def test_accepting_again_is_only_for_a_role_the_person_has(api, published):
    unknown = api.post("/api/me/terms", json={"role": "client", **terms()}, headers=tg(CLIENT))
    assert (unknown.status_code, code(unknown)) == (404, "account_not_found")
    assert client_signup(api, terms=terms()).status_code == 200
    response = api.post("/api/me/terms", json={"role": "provider", **terms("telegram_bot", *PROVIDER_TERMS_V1)}, headers=tg(CLIENT))
    assert (response.status_code, code(response)) == (409, "role_not_held")


def test_whatsapp_accepts_again_once_per_message(api, backend, published):
    signup = {"display_name": "Marie", "language": "ln", "terms": terms("whatsapp")}
    assert api.post("/api/whatsapp/client", json=signup, headers=wa_write()).status_code == 200
    publish(backend, conditions.CGU, "v2")
    assert api.get("/api/me/terms", headers=wa()).json()["complete"] is False
    payload = {"role": "client", **terms("whatsapp", ("cgu", "v2"))}
    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post("/api/me/terms", json=payload, headers=wa_write(key=key))
    replay = api.post("/api/me/terms", json=payload, headers=wa_write(key=key))
    assert first.status_code == replay.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert [row[1:] for row in acceptances(backend)] == [("client", "whatsapp", "ln"), ("client", "whatsapp", "ln")]


def test_a_provider_goes_offline_freely_but_needs_the_terms_to_be_available(api, backend, published):
    assert provider_signup(api, terms=terms("telegram_bot", *PROVIDER_TERMS_V1)).status_code == 200
    account_id = api.get("/api/me/profile", headers=tg(PROVIDER)).json()["account_id"]
    assert api.post(f"/api/admin/providers/{account_id}/verify", headers=tg(ADMIN)).status_code == 200
    publish(backend, conditions.PROVIDER_TERMS, "v2")
    refused = api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=tg(PROVIDER))
    assert (refused.status_code, code(refused)) == (409, "terms_not_accepted")
    assert api.patch("/api/me/provider-profile/status", json={"status": "offline"}, headers=tg(PROVIDER)).status_code == 200
    again = {"role": "provider", **terms("telegram_bot", ("conditions_prestataires", "v2"))}
    assert api.post("/api/me/terms", json=again, headers=tg(PROVIDER)).status_code == 200
    assert api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=tg(PROVIDER)).status_code == 200


# --- Lire les textes -----------------------------------------------------------------


def test_the_texts_are_readable_by_version(api, backend, published):
    publish(backend, conditions.CGU, "v2")
    current = api.get("/api/legal/documents/cgu", headers=tg(CLIENT)).json()
    assert (current["version"], current["text"]) == ("v2", "Texte de cgu, version v2.")
    old = api.get("/api/legal/documents/cgu/v1", headers=wa()).json()
    assert old["text_sha256"] == conditions.fingerprint("Texte de cgu, version v1.")
    assert api.get("/api/legal/documents/cgu/v9", headers=tg(CLIENT)).status_code == 404
    assert api.get("/api/legal/documents/charte", headers=tg(CLIENT)).status_code == 404
    assert api.get("/api/legal/documents/cgu").status_code == 401
    assert datetime.fromisoformat(current["effective_at"])
