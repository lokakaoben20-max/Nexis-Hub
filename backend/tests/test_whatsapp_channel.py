"""Canal WhatsApp, étape 1 : une clé de service par canal, routes fermées à
WhatsApp par défaut, aucune action de prestataire depuis WhatsApp, inscription
du client WhatsApp (docs/ARCHITECTURE_WHATSAPP.md, plan d'implémentation du
7 novembre 2026).
"""

import importlib
import re
import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-0001"
WHATSAPP_KEY = "test-whatsapp-service-key-not-a-secret-0002"
BSUID = "CD.13491208655302741918"
OTHER_BSUID = "CD.99887766554433221100"

# Les seules routes que le service WhatsApp peut appeler. Ajouter une route ici
# est une décision : elle doit avoir ses tests de parité avec Telegram.
WHATSAPP_ROUTES = {
    ("POST", "/api/whatsapp/client"),
    ("GET", "/api/me/wallet"),
    ("GET", "/api/me/missions"),
    # Profil de l'acteur et catalogue (profils, étape 2).
    ("GET", "/api/services"),
    ("GET", "/api/me/profile"),
    ("PATCH", "/api/me/language"),
    ("PATCH", "/api/me/name"),
}

# Actions de prestataire : jamais depuis WhatsApp, refus explicite.
PROVIDER_ROUTES = {
    ("POST", "/api/bot/providers"),
    ("PATCH", "/api/bot/providers/{telegram_id}/language"),
    ("PATCH", "/api/bot/providers/{telegram_id}/services"),
    ("PATCH", "/api/bot/providers/{telegram_id}/status"),
    ("POST", "/api/bot/quotes"),
    # Arrivée : « je suis arrivé » et code de présence (plus de « démarrer »).
    ("POST", "/api/bot/missions/{mission_id}/presence/arrived"),
    ("POST", "/api/bot/missions/{mission_id}/presence/code"),
    ("POST", "/api/bot/missions/{mission_id}/finish"),
    # Réponse du prestataire à un accord amiable.
    ("POST", "/api/bot/missions/{mission_id}/dispute/offers/{offer_id}/accept"),
    ("POST", "/api/bot/missions/{mission_id}/dispute/offers/{offer_id}/decline"),
    ("POST", "/api/bot/service-requests"),
    # Profil prestataire au nom de l'acteur et refus d'alerte (profils, étape 2).
    ("PUT", "/api/me/provider-profile"),
    ("PUT", "/api/me/provider-profile/services"),
    ("PUT", "/api/me/provider-profile/communes"),
    ("PATCH", "/api/me/provider-profile/status"),
    ("POST", "/api/bot/missions/{mission_id}/decline"),
}


@pytest.fixture
def backend(backend_db_url, monkeypatch):
    # Charge d'abord tout le backend : recharger un module importé pour la
    # première fois juste avant redéfinirait ses tables deux fois.
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    main.database = database
    return main


@pytest.fixture
def client(backend):
    with TestClient(backend.app) as test_client:
        yield test_client


def as_whatsapp(bsuid=BSUID):
    return {"X-API-Key": WHATSAPP_KEY, "X-Actor-Channel": "whatsapp", "X-Actor-Id": bsuid}


def as_telegram(telegram_id=42):
    return {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def register(client, bsuid=BSUID, phone="243810000001", name="Mado", language="ln", key=None):
    """Un message WhatsApp distinct à chaque appel (clé neuve), sauf `key`."""
    body = {"display_name": name, "language": language}
    if phone is not None:
        body["phone"] = phone
    headers = {**as_whatsapp(bsuid), "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}"}
    return client.post("/api/whatsapp/client", json=body, headers=headers)


def api_routes(backend):
    """Toutes les routes du router protégé par les clés de service."""
    return [
        (method, route.path, route.endpoint)
        for route in backend.router.routes
        if isinstance(route, APIRoute)
        for method in route.methods
    ]


def concrete(path):
    return re.sub(r"\{[^}]+\}", "1", path)


# --- Configuration des clés ----------------------------------------------------


def test_backend_refuses_to_start_with_the_old_single_key(backend, monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", TELEGRAM_KEY)
    with pytest.raises(backend.service_keys.ConfigurationError, match="BACKEND_API_KEY_TELEGRAM"):
        with TestClient(backend.app):
            pass


def test_backend_refuses_to_start_without_the_telegram_key(backend, monkeypatch):
    monkeypatch.delenv("BACKEND_API_KEY_TELEGRAM")
    with pytest.raises(backend.service_keys.ConfigurationError):
        with TestClient(backend.app):
            pass


def test_backend_refuses_to_start_with_a_short_key(backend, monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", "court")
    with pytest.raises(backend.service_keys.ConfigurationError, match="trop courte"):
        with TestClient(backend.app):
            pass


def test_backend_refuses_to_start_when_two_channels_share_a_key(backend, monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", TELEGRAM_KEY)
    with pytest.raises(backend.service_keys.ConfigurationError, match="même clé"):
        with TestClient(backend.app):
            pass


def test_backend_starts_without_whatsapp_key_and_then_refuses_every_whatsapp_call(backend, monkeypatch):
    monkeypatch.delenv("BACKEND_API_KEY_WHATSAPP")
    with TestClient(backend.app) as test_client:
        assert test_client.get("/api/me/wallet", headers=as_whatsapp()).status_code == 401
        assert test_client.get("/api/me/wallet", headers=as_telegram()).status_code == 200


def test_a_misconfiguration_after_start_refuses_requests_instead_of_guessing(client, monkeypatch):
    monkeypatch.setenv("BACKEND_API_KEY", TELEGRAM_KEY)
    assert client.get("/api/me/wallet", headers=as_telegram()).status_code == 500


def test_unknown_key_is_refused(client):
    headers = {**as_telegram(), "X-API-Key": "x" * 40}
    assert client.get("/api/me/wallet", headers=headers).status_code == 401


# --- Le canal déclaré est celui de la clé -------------------------------------


def test_whatsapp_service_cannot_act_as_a_telegram_user(client):
    headers = {**as_telegram(), "X-API-Key": WHATSAPP_KEY}
    response = client.get("/api/me/wallet", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "actor_channel_mismatch"


def test_telegram_bot_cannot_act_as_a_whatsapp_user(client):
    headers = {**as_whatsapp(), "X-API-Key": TELEGRAM_KEY}
    response = client.get("/api/me/wallet", headers=headers)
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "actor_channel_mismatch"


@pytest.mark.parametrize(
    "bsuid",
    ["243810000001", "cd.123", "CD.", "CD.abc-def", "CD." + "1" * 129, "C.123", "CDX.123", "CD.12 34"],
)
def test_malformed_whatsapp_identity_is_refused(client, bsuid):
    response = client.get("/api/me/wallet", headers=as_whatsapp(bsuid))
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_actor"


def test_longest_valid_whatsapp_identity_is_accepted_and_stored(client, backend):
    bsuid = "CD." + "a" * 128
    assert register(client, bsuid=bsuid, phone=None).status_code == 200
    with backend.database.SessionLocal() as db:
        assert backend.ledger.account_id_for(db, "whatsapp", bsuid) is not None


# --- Routes : fermées à WhatsApp par défaut, jamais d'action de prestataire ---


def test_exactly_the_listed_routes_are_open_to_whatsapp(backend):
    opened = {
        (method, path)
        for method, path, endpoint in api_routes(backend)
        if "whatsapp" in backend.route_channels(endpoint)
    }
    assert opened == WHATSAPP_ROUTES


def test_exactly_the_listed_routes_are_provider_actions_and_none_is_open_to_whatsapp(backend):
    marked = {(method, path) for method, path, endpoint in api_routes(backend) if backend.is_provider_action(endpoint)}
    assert marked == PROVIDER_ROUTES
    for method, path, endpoint in api_routes(backend):
        if backend.is_provider_action(endpoint):
            assert backend.route_channels(endpoint) == frozenset({"telegram"}), (method, path)


def test_every_route_not_opened_is_refused_to_the_whatsapp_service(client, backend):
    """Toutes les routes, sans exception : un oubli de marquage ne peut pas
    ouvrir une route à WhatsApp."""
    checked = 0
    for method, path, _endpoint in api_routes(backend):
        if (method, path) in WHATSAPP_ROUTES:
            continue
        response = client.request(method, concrete(path), headers=as_whatsapp(), json={})
        expected = "provider_channel_forbidden" if (method, path) in PROVIDER_ROUTES else "channel_forbidden"
        assert response.status_code == 403, (method, path, response.status_code)
        assert response.json()["detail"]["code"] == expected, (method, path)
        checked += 1
    assert checked >= 40


def test_the_telegram_bot_keeps_every_route_except_the_whatsapp_registration(client, backend):
    for method, path, _endpoint in api_routes(backend):
        response = client.request(method, concrete(path), headers=as_telegram(), json={})
        if (method, path) == ("POST", "/api/whatsapp/client"):
            assert response.status_code == 403
            assert response.json()["detail"]["code"] == "channel_forbidden"
        else:
            assert response.status_code != 403 or response.json()["detail"] != {"code": "channel_forbidden"}, (method, path)


def test_a_provider_action_can_never_be_opened_to_whatsapp(backend):
    def quote():
        pass

    with pytest.raises(RuntimeError, match="prestataire"):
        backend.open_to("telegram", "whatsapp")(backend.provider_action(quote))

    def start():
        pass

    with pytest.raises(RuntimeError, match="prestataire"):
        backend.provider_action(backend.open_to("telegram", "whatsapp")(start))


def test_whatsapp_client_cannot_list_missions_as_provider(client):
    register(client)
    response = client.get("/api/me/missions?role=provider", headers=as_whatsapp())
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "provider_channel_forbidden"


def test_only_the_payment_webhook_is_an_api_route_outside_the_service_keys(backend):
    unprotected = {
        route.path for route in backend.app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/")
    }
    assert unprotected == {"/api/payments/webhook/{gateway_name}"}
    assert all(path.startswith("/api/") for _method, path, _endpoint in api_routes(backend))


def test_the_payment_webhook_stays_outside_the_service_keys(client):
    # L'agrégateur n'a pas de clé de canal : sa route reste hors du router.
    response = client.post("/api/payments/webhook/inconnu", headers=as_whatsapp())
    assert response.status_code == 404


# --- Inscription du client WhatsApp -------------------------------------------


def test_new_whatsapp_client_gets_an_account_with_its_proven_phone(client, backend):
    response = register(client)
    assert response.status_code == 200
    body = response.json()
    assert body["created"] is True
    assert body["account"]["roles"] == ["client"]
    assert body["account"]["language"] == "ln"
    assert body["account"]["display_name"] == "Mado"
    assert body["account"]["phone_proven"] is True
    assert "phone" not in body["account"]

    with backend.database.SessionLocal() as db:
        account_id = backend.ledger.account_id_for(db, "whatsapp", BSUID)
        account = db.get(backend.crud.NexisAccount, account_id)
        assert account.phone_e164 == "+243810000001"
        assert account.phone_verified_at is not None
        identities = db.query(backend.crud.ledger.ChannelIdentity).filter_by(account_id=account_id).all()
        assert [(identity.channel, identity.verified_at is not None) for identity in identities] == [("whatsapp", True)]


def test_registering_again_updates_the_same_account(client, backend):
    first = register(client).json()["account"]["account_id"]
    response = register(client, name="Mado K.", language="fr")
    assert response.status_code == 200
    assert response.json()["created"] is False
    assert response.json()["account"]["account_id"] == first
    assert response.json()["account"]["display_name"] == "Mado K."
    assert response.json()["account"]["language"] == "fr"
    with backend.database.SessionLocal() as db:
        assert db.query(backend.crud.NexisAccount).count() == 1


def test_whatsapp_client_without_visible_phone_still_gets_an_account(client, backend):
    response = register(client, phone=None)
    assert response.status_code == 200
    assert response.json()["account"]["phone_proven"] is False
    with backend.database.SessionLocal() as db:
        account = db.get(backend.crud.NexisAccount, response.json()["account"]["account_id"])
        assert account.phone_e164 is None


def _telegram_client_with_proven_phone(client, telegram_id=42, phone="+243810000001"):
    response = client.post(
        "/api/bot/users",
        json={"telegram_id": telegram_id, "first_name": "Ben", "phone_number": phone, "phone_verified": True},
        headers={"X-API-Key": TELEGRAM_KEY},
    )
    assert response.status_code == 200
    return response.json()["user"]["account_id"]


def test_phone_already_proven_by_a_telegram_account_is_refused_and_nothing_is_created(client, backend):
    telegram_account = _telegram_client_with_proven_phone(client)

    response = register(client, phone="+243810000001")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "phone_owned_by_account"
    with backend.database.SessionLocal() as db:
        assert backend.ledger.account_id_for(db, "whatsapp", BSUID) is None
        assert db.query(backend.crud.NexisAccount).count() == 1
        events = db.query(backend.app_auth.AuthEvent).filter_by(type="whatsapp_phone_conflict").all()
        assert [(event.account_id, event.result) for event in events] == [(telegram_account, "refused")]
        # Le compte Telegram et son numéro ne bougent pas.
        account = db.get(backend.crud.NexisAccount, telegram_account)
        assert account.phone_e164 == "+243810000001"


def test_known_whatsapp_identity_never_takes_a_phone_proven_elsewhere(client, backend):
    whatsapp_account = register(client, phone=None).json()["account"]["account_id"]
    telegram_account = _telegram_client_with_proven_phone(client)

    response = register(client, phone="+243810000001")

    assert response.status_code == 200
    assert response.json()["account"]["phone_proven"] is False
    with backend.database.SessionLocal() as db:
        assert db.get(backend.crud.NexisAccount, whatsapp_account).phone_e164 is None
        assert db.get(backend.crud.NexisAccount, telegram_account).phone_e164 == "+243810000001"


def test_two_whatsapp_identities_cannot_share_a_proven_phone(client):
    assert register(client).status_code == 200
    response = register(client, bsuid=OTHER_BSUID)
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "phone_owned_by_account"


@pytest.mark.parametrize(
    "overrides, code",
    [
        ({"language": "de"}, "invalid_language"),
        ({"phone": "pas un numéro"}, "invalid_phone"),
        ({"name": "   "}, "invalid_name"),
    ],
)
def test_invalid_registration_is_refused_without_creating_anything(client, backend, overrides, code):
    response = register(client, **overrides)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == code
    with backend.database.SessionLocal() as db:
        assert db.query(backend.crud.NexisAccount).count() == 0


def test_whatsapp_registration_never_gives_the_provider_role(client, backend):
    register(client)
    with backend.database.SessionLocal() as db:
        account = db.get(backend.crud.NexisAccount, backend.ledger.account_id_for(db, "whatsapp", BSUID))
        assert "provider" not in account.roles


# --- Lectures ouvertes au client WhatsApp ---------------------------------------


def test_whatsapp_client_reads_its_own_wallet_only(client):
    account_id = register(client).json()["account"]["account_id"]
    wallet = client.get("/api/me/wallet", headers=as_whatsapp()).json()["wallet"]
    assert wallet == {"account_id": account_id, "wallet_balance_usd": 0.0, "wallet_balance_cdf": 0.0}


def test_unknown_whatsapp_client_has_no_wallet_and_no_missions(client, backend):
    assert client.get("/api/me/wallet", headers=as_whatsapp()).json()["wallet"]["account_id"] is None
    assert client.get("/api/me/missions", headers=as_whatsapp()).json()["missions"] == []
    with backend.database.SessionLocal() as db:
        # Une lecture ne crée jamais de compte.
        assert db.query(backend.crud.NexisAccount).count() == 0


def test_whatsapp_client_lists_its_client_missions(client):
    register(client)
    response = client.get("/api/me/missions", headers=as_whatsapp())
    assert response.status_code == 200
    assert response.json()["missions"] == []


def test_refreshing_an_unknown_payment_intent_is_a_clean_404(client):
    response = client.post("/api/bot/payment-intents/999/refresh", headers=as_telegram())
    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "intent_not_found"
