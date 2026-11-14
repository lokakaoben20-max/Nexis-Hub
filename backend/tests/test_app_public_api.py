"""API publique de l'application mobile (étape 1, PR 5) : `backend/app/public.py`.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5 et 6.

Ce qui est vérifié : l'application publique n'a aucune route du bot, n'accepte
ni la clé partagée ni les en-têtes d'acteur ; une connexion passe par code et
signature ; une demande qui touche aux téléphones est signée et ne rejoue pas ;
une mission ou un portefeuille d'un autre compte n'est jamais lu ; aucune
réponse ne contient d'identifiant Telegram.
"""

import importlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from backend.app import app_auth, app_sessions
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

    Device = importlib.import_module("backend.app.models").Device  # modèle rechargé par `env`

    def queued():
        with database.SessionLocal() as session:
            rows = session.query(Device.id).filter(Device.alert_due_at.is_not(None)).order_by(Device.id)
            return [device_id for (device_id,) in rows]

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


def test_whatsapp_codes_are_not_offered_yet(client):
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
