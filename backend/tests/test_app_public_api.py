"""API publique de l'application mobile (étape 1, PR 5) : `backend/app/public.py`.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5 et 6.

Ce qui est vérifié : l'application publique n'a aucune route du bot, n'accepte
ni la clé partagée ni les en-têtes d'acteur ; une connexion passe par code et
signature ; une demande qui touche aux téléphones est signée et ne rejoue pas ;
une mission ou un portefeuille d'un autre compte n'est jamais lu ; aucune
réponse ne contient d'identifiant Telegram.
"""

import importlib
import itertools
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from sqlalchemy import select

from backend.app import app_auth, app_sessions, conditions, ledger
from backend.tests import boite_envoi, profils_de_test
from test_app_sessions import PHONE, Phone

API = "/api/app/v1"
VERSION = {"X-App-Version": "1.2.0"}
BOT_KEY = "test-backend-api-key-not-a-secret"


@pytest.fixture
def env(monkeypatch, backend_db_url):
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", BOT_KEY)
    monkeypatch.setenv("APP_CODE_HMAC_KEY", "test-hmac-key-not-a-secret-0123456789abcdef")
    monkeypatch.setenv("NEXIS_BOT_USERNAME", "@NexisHubTestBot")
    monkeypatch.delenv("NEXIS_APP_MIN_VERSION", raising=False)
    for name in ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_CALLBACK_KEY", app_auth.WHATSAPP_NUMBER_ENV):
        monkeypatch.delenv(name, raising=False)
    # Horloge des demandes de code : 61 s de plus à chaque lecture, pour que
    # deux connexions de suite du même numéro respectent le renvoi après 60 s.
    start, ticks = datetime.utcnow(), itertools.count(1)
    monkeypatch.setattr(app_auth, "_utcnow", lambda: start + timedelta(seconds=61 * next(ticks)))
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    public = importlib.reload(importlib.import_module("backend.app.public"))
    database.init_db()
    return database, public


@pytest.fixture
def client(env):
    _, public = env
    return TestClient(public.app)


@pytest.fixture
def alerts(env):
    """Téléphones dont l'alerte « Nouvel appareil » attend dans la boîte
    d'envoi (envoyée ensuite par la tâche planifiée)."""
    database, _ = env

    def queued():
        with database.SessionLocal() as session:
            return [int(note.event_key.split(":")[1]) for note in boite_envoi.messages(session, event_prefix="new_device:")]

    return queued


def _public_key(phone):
    return phone.public_key


def login(client, database, phone, telegram_id=601, number=PHONE, platform="android", label="Samsung A54"):
    """Parcours complet : demande de code, lien Telegram, bot qui affiche le
    code, signature du téléphone, connexion."""
    challenge = client.post(
        f"{API}/auth/challenges",
        json={"phone": number, "channel": "telegram", "public_key": _public_key(phone)},
        headers=VERSION,
    )
    assert challenge.status_code == 200, challenge.text
    link = challenge.json()["telegram_link"]
    start = link.split("?start=", 1)[1].removeprefix(app_auth.TELEGRAM_START_PREFIX)
    with database.SessionLocal() as session:
        issued = app_auth.issue_code_for_telegram_contact(
            session, start_token=start, telegram_id=telegram_id, contact_phone=number
        )
    public_id = challenge.json()["public_id"]
    response = client.post(
        f"{API}/auth/challenges/{public_id}/verify",
        json={
            "code": issued.code,
            "public_key": _public_key(phone),
            "signature": phone.sign(app_sessions.login_message(public_id)),
            "platform": platform,
            "label": label,
        },
        headers=VERSION,
    )
    assert response.status_code == 200, response.text
    return response.json()


def bearer(tokens):
    return {**VERSION, "Authorization": f"Bearer {tokens['access_token']}"}


def walk_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from walk_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_keys(item)


# --- Ce que l'application publique n'est pas -------------------------------------


def test_config_is_open_and_offers_telegram_only(client):
    response = client.get(f"{API}/config")

    assert response.status_code == 200
    assert response.json()["channels"] == ["telegram"]


@pytest.mark.parametrize("version,status,code", [(None, 400, "app_version_required"), ("abc", 400, "app_version_required"), ("0.9.0", 426, "app_update_required")])
def test_old_or_missing_versions_are_refused_before_anything_else(client, version, status, code):
    headers = {} if version is None else {"X-App-Version": version}

    response = client.get(f"{API}/me", headers=headers)

    assert response.status_code == status
    assert response.json()["detail"] == {"code": code}


def test_a_minimum_version_set_by_the_server_is_enforced(client, monkeypatch):
    monkeypatch.setenv("NEXIS_APP_MIN_VERSION", "2.0")

    assert client.get(f"{API}/me", headers={"X-App-Version": "1.9.9"}).status_code == 426
    assert client.get(f"{API}/me", headers={"X-App-Version": "2.0.0"}).status_code == 401


def test_the_bot_api_does_not_exist_on_the_public_app(client):
    response = client.get("/api/me/profile", headers={**VERSION, "X-API-Key": BOT_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": "601"})

    assert response.status_code == 404


def test_the_bot_key_and_actor_headers_open_nothing_here(client):
    headers = {**VERSION, "X-API-Key": BOT_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": "601"}

    assert client.get(f"{API}/me", headers=headers).json()["detail"] == {"code": "unauthorized"}
    assert client.get(f"{API}/me/wallet", headers=headers).status_code == 401


# --- Connexion ------------------------------------------------------------------


def test_a_full_login_gives_tokens_and_no_telegram_identifier(client, env, alerts):
    database, _ = env
    tokens = login(client, database, Phone())

    assert set(tokens) == {"access_token", "access_expires_at", "refresh_token", "refresh_expires_at", "device_id", "new_device"}
    assert tokens["new_device"] is True
    assert alerts() == []  # premier téléphone d'un compte tout neuf : aucune alerte
    assert not any("telegram" in key.lower() for key in walk_keys(tokens))


def test_my_profile_shows_the_masked_proven_phone(client, env, alerts):
    database, _ = env
    tokens = login(client, database, Phone())

    response = client.get(f"{API}/me", headers=bearer(tokens))

    assert response.status_code == 200
    assert response.json() == {"language": "fr", "phone_masked": "+243•••••01"}


def test_a_known_phone_on_the_same_account_is_not_a_new_device(client, env, alerts):
    database, _ = env
    login(client, database, Phone())
    again = login(client, database, Phone())

    assert again["new_device"] is True  # nouveau téléphone (nouvelle clé) : alerte
    assert alerts() == [again["device_id"]]


def test_a_wrong_code_gives_no_session(client, env, alerts):
    database, _ = env
    phone = Phone()
    challenge = client.post(
        f"{API}/auth/challenges", json={"phone": PHONE, "channel": "telegram", "public_key": _public_key(phone)}, headers=VERSION
    ).json()

    response = client.post(
        f"{API}/auth/challenges/{challenge['public_id']}/verify",
        json={
            "code": "000000",
            "public_key": _public_key(phone),
            "signature": phone.sign(app_sessions.login_message(challenge["public_id"])),
            "platform": "android",
        },
        headers=VERSION,
    )

    assert response.status_code == 400
    assert alerts() == []


def test_whatsapp_codes_are_refused_while_whatsapp_is_not_configured(client):
    phone = Phone()

    response = client.post(
        f"{API}/auth/challenges", json={"phone": PHONE, "channel": "whatsapp", "public_key": _public_key(phone)}, headers=VERSION
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "delivery_unavailable"}


def test_a_challenge_without_a_configured_bot_says_so(client, env, monkeypatch):
    monkeypatch.delenv("NEXIS_BOT_USERNAME")

    response = client.post(
        f"{API}/auth/challenges", json={"phone": PHONE, "channel": "telegram", "public_key": _public_key(Phone())}, headers=VERSION
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {"code": "auth_not_configured"}


# --- Renouvellement et déconnexion -----------------------------------------------


def test_refresh_rotates_and_a_used_refresh_token_is_refused(client, env, alerts):
    database, _ = env
    phone = Phone()
    tokens = login(client, database, phone)
    signature = phone.sign(app_sessions.refresh_message(tokens["refresh_token"]))

    renewed = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"], "signature": signature}, headers=VERSION)
    replay = client.post(f"{API}/auth/refresh", json={"refresh_token": tokens["refresh_token"], "signature": signature}, headers=VERSION)

    assert renewed.status_code == 200
    assert replay.status_code == 401
    assert client.get(f"{API}/me", headers=bearer(tokens)).status_code == 401


def test_logout_ends_this_phone_only(client, env, alerts):
    database, _ = env
    tokens = login(client, database, Phone())

    assert client.post(f"{API}/auth/logout", headers=bearer(tokens)).status_code == 200
    assert client.get(f"{API}/me", headers=bearer(tokens)).status_code == 401


# --- Téléphones : demande signée ----------------------------------------------------


def signed_delete(client, tokens, phone, device_id, *, nonce, sent_at=None, signature=None):
    path = f"{API}/me/devices/{device_id}"
    timestamp = str(int(((sent_at or datetime.utcnow()) - app_sessions._EPOCH).total_seconds()))
    message = app_sessions.request_message(
        method="DELETE", path=path, body=b"", timestamp=timestamp, nonce=nonce, access_token=tokens["access_token"]
    )
    headers = {
        **bearer(tokens),
        "X-Request-Timestamp": timestamp,
        "X-Request-Nonce": nonce,
        "X-Request-Signature": signature or phone.sign(message),
    }
    return client.delete(path, headers=headers)


def test_a_phone_can_be_cut_by_a_signed_request_and_the_request_cannot_be_replayed(client, env, alerts):
    database, _ = env
    first, second = Phone(), Phone()
    owner = login(client, database, first)
    lost = login(client, database, second, platform="ios", label="iPhone 12")

    cut = signed_delete(client, owner, first, lost["device_id"], nonce="nonce-delete-0123456789abcdef")
    replay = signed_delete(client, owner, first, lost["device_id"], nonce="nonce-delete-0123456789abcdef")

    assert cut.status_code == 200 and cut.json() == {"status": "ok", "revoked": True}
    assert replay.status_code == 409
    assert client.get(f"{API}/me", headers=bearer(lost)).status_code == 401


def test_cutting_a_phone_without_a_signature_is_refused(client, env, alerts):
    database, _ = env
    owner = login(client, database, Phone())

    response = client.delete(f"{API}/me/devices/{owner['device_id']}", headers=bearer(owner))

    assert response.status_code == 400
    assert response.json()["detail"] == {"code": "invalid_timestamp"}


def test_a_signature_by_another_phone_cannot_cut_my_phones(client, env, alerts):
    database, _ = env
    owner = login(client, database, Phone())
    other = login(client, database, Phone(), telegram_id=601)

    response = signed_delete(client, owner, Phone(), other["device_id"], nonce="nonce-thief-0123456789abcdef")

    assert response.status_code == 401
    assert response.json()["detail"] == {"code": "invalid_signature"}


def test_my_devices_lists_only_my_phones_and_marks_the_current_one(client, env, alerts):
    database, _ = env
    mine = login(client, database, Phone())
    login(client, database, Phone(), telegram_id=602, number="+243810000002")

    devices = client.get(f"{API}/me/devices", headers=bearer(mine)).json()["devices"]

    assert [(d["id"], d["current"]) for d in devices] == [(mine["device_id"], True)]
    assert not any("telegram" in key.lower() for key in walk_keys(devices))


# --- Portefeuille et missions -------------------------------------------------------


def test_my_wallet_starts_at_zero(client, env, alerts):
    database, _ = env
    tokens = login(client, database, Phone())

    response = client.get(f"{API}/me/wallet", headers=bearer(tokens))

    assert response.json() == {"wallet_balance_usd": 0.0, "wallet_balance_cdf": 0.0}


def test_a_mission_of_mine_is_read_without_telegram_identifiers(client, env, alerts):
    database, _ = env
    from backend.app import crud

    tokens = login(client, database, Phone(), telegram_id=601)
    with database.SessionLocal() as session:
        mission, _ = crud.create_mission(
            session, channel="telegram", client_external_id="601", creation_key="k-app-1",
            service="service_plomberie", commune="Gombe", description="Fuite sous l'évier",
            destination_latitude=-4.307612, destination_longitude=15.312512,
            destination_landmark="Portail bleu après la poste",
        )
        mission_id = mission.mission_id

    listed = client.get(f"{API}/me/missions?role=client", headers=bearer(tokens)).json()["missions"]
    detail = client.get(f"{API}/missions/{mission_id}", headers=bearer(tokens))

    assert [m["mission_id"] for m in listed] == [mission_id]
    assert detail.status_code == 200 and detail.json()["viewer_role"] == "client"
    assert not any("telegram" in key.lower() for key in walk_keys([listed, detail.json()]))


def test_another_persons_mission_does_not_exist_for_me(client, env, alerts):
    database, _ = env
    from backend.app import crud

    login(client, database, Phone(), telegram_id=601)
    with database.SessionLocal() as session:
        mission, _ = crud.create_mission(
            session, channel="telegram", client_external_id="601", creation_key="k-app-2",
            service="service_plomberie", commune="Gombe",
            destination_latitude=-4.307612, destination_longitude=15.312512,
            destination_landmark="Portail bleu après la poste",
        )
        mission_id = mission.mission_id
    stranger = login(client, database, Phone(), telegram_id=602, number="+243810000002")

    response = client.get(f"{API}/missions/{mission_id}", headers=bearer(stranger))

    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "mission_not_found"}
    assert client.get(f"{API}/me/missions?role=client", headers=bearer(stranger)).json()["missions"] == []


def test_the_role_must_be_client_or_provider(client, env, alerts):
    database, _ = env
    tokens = login(client, database, Phone())

    response = client.get(f"{API}/me/missions?role=admin", headers=bearer(tokens))

    assert response.status_code == 400
    assert response.json()["detail"] == {"code": "invalid_role"}


# --- Conditions d'utilisation (backend/app/conditions.py) -------------------------


def publish_terms(database, key, version):
    with database.SessionLocal() as db:
        conditions.publish_version(db, key, version, f"Texte {key} {version}")
        db.commit()


@pytest.mark.conditions_reelles
def test_the_app_reads_the_texts_and_re_accepts_for_a_role_it_has(client, env, alerts):
    database, _ = env
    publish_terms(database, "cgu", "v1")
    publish_terms(database, "conditions_prestataires", "v1")
    tokens = login(client, database, Phone(), telegram_id=601)

    assert client.get(f"{API}/legal/documents/cgu", headers=VERSION).json()["text"] == "Texte cgu v1"
    assert client.get(f"{API}/legal/documents/cgu/v9", headers=VERSION).status_code == 404
    # Compte encore sans rôle : rien à recocher, et recocher n'a pas de sens.
    assert client.get(f"{API}/me/terms", headers=bearer(tokens)).json()["missing"] == []
    no_role = client.post(
        f"{API}/me/terms", json={"role": "client", "documents": [{"document_key": "cgu", "version": "v1"}]}, headers=bearer(tokens)
    )
    assert (no_role.status_code, no_role.json()["detail"]["code"]) == (409, "role_not_held")

    with database.SessionLocal() as db:
        profils_de_test.client(db, 601)  # client inscrit avant la règle
    status = client.get(f"{API}/me/terms", headers=bearer(tokens)).json()
    assert [item["document_key"] for item in status["missing"]] == ["cgu"]
    outdated = client.post(
        f"{API}/me/terms", json={"role": "client", "documents": [{"document_key": "cgu", "version": "v0"}]}, headers=bearer(tokens)
    )
    assert outdated.status_code == 404
    accepted = client.post(
        f"{API}/me/terms", json={"role": "client", "documents": [{"document_key": "cgu", "version": "v1"}]}, headers=bearer(tokens)
    )
    assert accepted.status_code == 200 and accepted.json()["complete"] is True
    with database.SessionLocal() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, 601)
        rows = db.scalars(select(conditions.LegalAcceptance)).all()
        assert [(row.account_id, row.role, row.surface) for row in rows] == [(account_id, "client", "app")]


def test_the_app_needs_a_session_for_my_terms(client, env):
    assert client.get(f"{API}/me/terms", headers=VERSION).status_code == 401


def test_a_whatsapp_login_goes_through_the_public_api_end_to_end(client, env, monkeypatch):
    """Parcours complet par WhatsApp : le canal est proposé, la réponse donne
    un lien wa.me avec un message déjà écrit (jeton, jamais de code) ; le
    service WhatsApp transmet ce message ; le code juste et la signature du
    téléphone ouvrent la session du compte créé pour cette identité."""
    from urllib.parse import parse_qs, urlparse

    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "test-access-token-not-a-secret")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "100000000000001")
    monkeypatch.setenv("WHATSAPP_CALLBACK_KEY", "test-callback-key-not-a-secret-0000000001")
    monkeypatch.setenv(app_auth.WHATSAPP_NUMBER_ENV, "+243990000000")
    database, _ = env
    phone = Phone()

    assert client.get(f"{API}/config").json()["channels"] == ["telegram", "whatsapp"]
    challenge = client.post(
        f"{API}/auth/challenges",
        json={"phone": PHONE, "channel": "whatsapp", "public_key": _public_key(phone), "language": "en"},
        headers=VERSION,
    )
    assert challenge.status_code == 200, challenge.text
    body = challenge.json()
    assert "telegram_link" not in body
    link = urlparse(body["whatsapp_link"])
    assert (link.scheme, link.netloc, link.path) == ("https", "wa.me", "/243990000000")
    (prefill,) = parse_qs(link.query)["text"]
    assert prefill.startswith("Sign in to the NexisHub app: app_")
    start = prefill.rsplit("app_", 1)[1]

    with database.SessionLocal() as session:
        issued = app_auth.issue_code_for_whatsapp(session, start_token=start, bsuid="CD.7000000000000000007", phone=PHONE)
    public_id = body["public_id"]
    response = client.post(
        f"{API}/auth/challenges/{public_id}/verify",
        json={
            "code": issued.code,
            "public_key": _public_key(phone),
            "signature": phone.sign(app_sessions.login_message(public_id)),
            "platform": "android",
            "label": "Samsung A54",
        },
        headers=VERSION,
    )
    assert response.status_code == 200, response.text
    assert client.get(f"{API}/me", headers=bearer(response.json())).status_code == 200


# --- Numéros de retrait : seulement dans l'app, par demande signée ------------------


def signed_post(client, tokens, phone, path, body=b"", *, nonce):
    timestamp = str(int((datetime.utcnow() - app_sessions._EPOCH).total_seconds()))
    message = app_sessions.request_message(
        method="POST", path=path, body=body, timestamp=timestamp, nonce=nonce, access_token=tokens["access_token"]
    )
    headers = {
        **bearer(tokens),
        "Content-Type": "application/json",
        "X-Request-Timestamp": timestamp,
        "X-Request-Nonce": nonce,
        "X-Request-Signature": phone.sign(message),
    }
    return client.post(path, content=body, headers=headers)


def attest(database, tokens):
    """Téléphone vérifié par Google ou Apple (l'app le fera pour de vrai)."""
    from backend.app import models

    with database.SessionLocal() as session:
        session.get(models.Device, tokens["device_id"]).attestation = "verified"
        session.commit()


NUMBERS = f"{API}/me/payout-destinations"
AIRTEL = b'{"operator": "airtel", "phone": "+243970000001"}'


def test_a_withdrawal_number_is_added_and_removed_by_a_signed_request_of_a_verified_phone(client, env, alerts):
    database, _ = env
    phone = Phone()
    tokens = login(client, database, phone)
    attest(database, tokens)

    added = signed_post(client, tokens, phone, NUMBERS, AIRTEL, nonce="nonce-add-number-0123456789ab")
    assert added.status_code == 200, added.text
    destination = added.json()["destination"]
    assert (destination["phone"], destination["usable_after"]) == ("+243970000001", None)
    replay = signed_post(client, tokens, phone, NUMBERS, AIRTEL, nonce="nonce-add-number-0123456789ab")
    assert replay.status_code == 409

    listing = client.get(NUMBERS, headers=bearer(tokens)).json()
    assert ([d["id"] for d in listing["destinations"]], listing["max"]) == ([destination["id"]], 4)

    second = signed_post(
        client, tokens, phone, NUMBERS, b'{"operator": "orange", "phone": "+243890000002"}', nonce="nonce-add-number-second-01234"
    )
    assert second.json()["destination"]["usable_after"] is not None, "numéro de plus : 72 h d'attente"

    removed = signed_post(
        client, tokens, phone, f"{NUMBERS}/{destination['id']}/remove", nonce="nonce-remove-number-0123456789"
    )
    assert removed.json() == {"status": "ok", "removed": destination["id"]}
    assert [d["phone"] for d in client.get(NUMBERS, headers=bearer(tokens)).json()["destinations"]] == ["+243890000002"]


def test_an_unsigned_or_unverified_phone_cannot_change_withdrawal_numbers(client, env, alerts):
    database, _ = env
    phone = Phone()
    tokens = login(client, database, phone)

    unsigned = client.post(NUMBERS, content=AIRTEL, headers={**bearer(tokens), "Content-Type": "application/json"})
    assert unsigned.json()["detail"] == {"code": "invalid_timestamp"}
    unverified = signed_post(client, tokens, phone, NUMBERS, AIRTEL, nonce="nonce-unverified-0123456789ab")
    assert (unverified.status_code, unverified.json()["detail"]) == (403, {"code": "device_not_attested"})
    assert client.get(NUMBERS, headers=bearer(tokens)).json()["destinations"] == []


def test_the_bot_api_cannot_remove_a_withdrawal_number(monkeypatch, backend_db_url):
    """Le bot enregistre le tout premier numéro (`first_only`), rien d'autre :
    aucune route du bot ne retire un numéro."""
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    main = importlib.reload(importlib.import_module("backend.app.main"))
    paths = {(method, route.path) for route in main.router.routes for method in getattr(route, "methods", ())}
    assert {path for _, path in paths if "payout-destinations" in path} == {"/api/bot/payout-destinations"}
