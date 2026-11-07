"""Téléphones et sessions de l'application mobile (étape 1, PR 3) : tests
d'attaque et cas normaux de `backend/app/app_sessions.py`, et route admin du
bot `/api/bot/admin/app-devices/revoke`.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5.5 et 5.6.
"""

import base64
import hashlib
import importlib
from datetime import datetime, timedelta

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app_auth, app_sessions, ledger, models

NOW = datetime(2026, 11, 7, 8, 0, 0)
PHONE = "+243810000001"


@pytest.fixture(autouse=True)
def code_key(monkeypatch):
    monkeypatch.setenv("APP_CODE_HMAC_KEY", "test-hmac-key-not-a-secret-0123456789abcdef")


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'app_sessions.db'}", future=True)
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


class Phone:
    """Un téléphone et sa clé d'appareil (le coffre matériel, en vrai)."""

    def __init__(self):
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        der = self.private_key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        self.public_key = base64.b64encode(der).decode()
        self.thumbprint = hashlib.sha256(der).hexdigest()

    def sign(self, message: str) -> str:
        return base64.b64encode(self.private_key.sign(message.encode(), ec.ECDSA(hashes.SHA256()))).decode()


def refused(expected, call, *args, **kwargs):
    with pytest.raises(app_auth.AuthError) as error:
        call(*args, **kwargs)
    assert error.value.code == expected
    return error.value


def code_for(db, phone, telegram_id=601, number=PHONE, now=NOW):
    created = app_auth.create_challenge(
        db, phone=number, delivery="telegram", device_key_thumbprint=phone.thumbprint, now=now
    )
    issued = app_auth.issue_code_for_telegram_contact(
        db, start_token=created.telegram_start_token, telegram_id=telegram_id, contact_phone=number, now=now
    )
    return created.public_id, issued.code


def sign_in(db, phone, telegram_id=601, now=NOW, **overrides):
    public_id, code = code_for(db, phone, telegram_id=telegram_id, now=now)
    values = dict(
        challenge_public_id=public_id,
        code=code,
        public_key=phone.public_key,
        signature=phone.sign(app_sessions.login_message(public_id)),
        platform="android",
        app_version="1.0.0",
        label="Samsung A54",
        now=now,
    )
    values.update(overrides)
    return app_sessions.sign_in(db, **values)


def refresh(db, phone, tokens, now=NOW):
    return app_sessions.refresh(
        db,
        refresh_token=tokens.refresh_token,
        signature=phone.sign(app_sessions.refresh_message(tokens.refresh_token)),
        now=now,
    )


def device(db, tokens):
    return db.get(models.Device, tokens.device_id)


# --- Connexion ----------------------------------------------------------------


def test_signing_in_creates_the_device_the_session_and_the_app_identity(db):
    phone = Phone()

    tokens = sign_in(db, phone)

    row = device(db, tokens)
    assert (row.platform, row.key_thumbprint, row.label) == ("android", phone.thumbprint, "Samsung A54")
    assert row.attestation == "unverified"
    assert ledger.account_id_for(db, ledger.APP, app_sessions.authenticate(db, tokens.access_token, now=NOW).identity_id) == tokens.account_id
    assert tokens.access_expires_at == NOW + timedelta(minutes=15)
    assert tokens.refresh_expires_at == NOW + timedelta(days=30)


def test_tokens_are_never_stored_in_clear(db):
    tokens = sign_in(db, Phone())

    session = db.query(models.AppSession).one()
    assert tokens.access_token not in (session.access_hash, session.refresh_hash)
    assert tokens.refresh_token not in (session.access_hash, session.refresh_hash)


def test_the_first_device_of_a_brand_new_account_has_no_money_delay(db):
    tokens = sign_in(db, Phone())

    assert device(db, tokens).money_unlocked_at == NOW


def test_a_device_added_to_an_existing_account_waits_72_hours_for_money(db):
    ledger.account_id_for(db, ledger.TELEGRAM, 601, create=True)
    db.commit()

    tokens = sign_in(db, Phone())

    assert device(db, tokens).money_unlocked_at == NOW + timedelta(hours=72)


def test_a_second_phone_on_the_same_account_waits_72_hours(db):
    sign_in(db, Phone())

    second = sign_in(db, Phone(), now=NOW + timedelta(minutes=20))

    assert device(db, second).money_unlocked_at == NOW + timedelta(minutes=20, hours=72)
    assert db.query(models.ChannelIdentity).filter_by(channel=ledger.APP).count() == 1


def test_signing_in_again_with_the_same_key_reuses_the_device(db):
    phone = Phone()
    first = sign_in(db, phone)
    app_sessions.sign_out(db, app_sessions.authenticate(db, first.access_token, now=NOW), now=NOW)

    again = sign_in(db, phone, now=NOW + timedelta(minutes=30))

    assert again.device_id == first.device_id
    assert device(db, again).money_unlocked_at == NOW


def test_a_signature_from_another_key_is_refused_and_the_code_stays_unused(db):
    phone, thief = Phone(), Phone()
    public_id, code = code_for(db, phone)

    refused(
        "invalid_signature",
        app_sessions.sign_in,
        db,
        challenge_public_id=public_id,
        code=code,
        public_key=phone.public_key,
        signature=thief.sign(app_sessions.login_message(public_id)),
        platform="android",
        app_version="1.0.0",
        now=NOW,
    )

    assert db.query(models.Device).count() == 0
    assert db.query(models.LoginChallenge).one().consumed_at is None


def test_a_signature_made_for_another_challenge_is_refused(db):
    phone = Phone()
    public_id, code = code_for(db, phone)

    refused("invalid_signature", sign_in, db, phone, signature=phone.sign(app_sessions.login_message("autre")))


def test_a_code_cannot_be_used_with_a_key_other_than_the_one_that_asked(db):
    phone, thief = Phone(), Phone()
    public_id, code = code_for(db, phone)

    refused(
        "invalid_code",
        app_sessions.sign_in,
        db,
        challenge_public_id=public_id,
        code=code,
        public_key=thief.public_key,
        signature=thief.sign(app_sessions.login_message(public_id)),
        platform="ios",
        app_version="1.0.0",
        now=NOW,
    )
    assert db.query(models.Device).count() == 0


def test_a_wrong_code_creates_no_device(db):
    phone = Phone()
    public_id, code = code_for(db, phone)
    wrong = f"{(int(code) + 1) % 1_000_000:06d}"

    refused("invalid_code", sign_in, db, phone, challenge_public_id=public_id, code=wrong,
            signature=phone.sign(app_sessions.login_message(public_id)))

    assert db.query(models.Device).count() == 0
    assert db.query(models.LoginChallenge).filter(models.LoginChallenge.public_id == public_id).one().attempts == 1


def test_a_revoked_key_can_never_sign_in_again(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    principal = app_sessions.authenticate(db, tokens.access_token, now=NOW)
    app_sessions.revoke_own_device(db, principal, tokens.device_id, now=NOW)

    refused("device_revoked", sign_in, db, phone, now=NOW + timedelta(hours=2))


def test_a_key_already_used_by_another_account_is_refused_without_consuming_the_code(db):
    phone = Phone()
    sign_in(db, phone, telegram_id=601)
    public_id, code = code_for(db, phone, telegram_id=602, number="+243810000002", now=NOW + timedelta(minutes=1))

    refused(
        "device_key_in_use",
        app_sessions.sign_in,
        db,
        challenge_public_id=public_id,
        code=code,
        public_key=phone.public_key,
        signature=phone.sign(app_sessions.login_message(public_id)),
        platform="android",
        app_version="1.0.0",
        now=NOW + timedelta(minutes=1),
    )
    challenge = db.query(models.LoginChallenge).filter(models.LoginChallenge.public_id == public_id).one()
    assert challenge.consumed_at is None
    assert db.query(models.Device).count() == 1


def _key_b64(private_key):
    der = private_key.public_key().public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    return base64.b64encode(der).decode()


@pytest.mark.parametrize(
    "public_key",
    [
        "pas-du-base64!",
        base64.b64encode(b"n'importe quoi").decode(),
        _key_b64(ec.generate_private_key(ec.SECP384R1())),
        _key_b64(rsa.generate_private_key(public_exponent=65537, key_size=2048)),
    ],
    ids=["not_base64", "not_a_key", "p384", "rsa"],
)
def test_only_p256_device_keys_are_accepted(db, public_key):
    refused("invalid_device_key", sign_in, db, Phone(), public_key=public_key)


@pytest.mark.parametrize("field,value,expected", [("platform", "windows", "invalid_platform"), ("app_version", "", "invalid_app_version"), ("app_version", "1" * 21, "invalid_app_version")])
def test_platform_and_version_are_checked(db, field, value, expected):
    refused(expected, sign_in, db, Phone(), **{field: value})


# --- Jetons d'accès -----------------------------------------------------------


def test_a_valid_access_token_gives_the_account_and_device(db):
    tokens = sign_in(db, Phone())

    principal = app_sessions.authenticate(db, tokens.access_token, now=NOW + timedelta(minutes=14))

    assert (principal.account_id, principal.device_id) == (tokens.account_id, tokens.device_id)


@pytest.mark.parametrize("token", [None, "", "inconnu"])
def test_unknown_access_tokens_are_refused(db, token):
    sign_in(db, Phone())

    refused("unauthorized", app_sessions.authenticate, db, token, now=NOW)


def test_an_expired_access_token_is_refused(db):
    tokens = sign_in(db, Phone())

    refused("unauthorized", app_sessions.authenticate, db, tokens.access_token, now=NOW + timedelta(minutes=15))


def test_a_refresh_token_is_not_an_access_token(db):
    tokens = sign_in(db, Phone())

    refused("unauthorized", app_sessions.authenticate, db, tokens.refresh_token, now=NOW)


# --- Renouvellement -----------------------------------------------------------


def test_refresh_gives_new_tokens_and_retires_the_old_ones(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    later = NOW + timedelta(minutes=20)

    renewed = refresh(db, phone, tokens, now=later)

    assert renewed.access_token != tokens.access_token and renewed.refresh_token != tokens.refresh_token
    assert app_sessions.authenticate(db, renewed.access_token, now=later).device_id == tokens.device_id
    refused("unauthorized", app_sessions.authenticate, db, tokens.access_token, now=NOW + timedelta(minutes=1))


def test_refresh_without_the_device_signature_is_refused(db):
    phone = Phone()
    tokens = sign_in(db, phone)

    refused(
        "invalid_signature",
        app_sessions.refresh,
        db,
        refresh_token=tokens.refresh_token,
        signature=Phone().sign(app_sessions.refresh_message(tokens.refresh_token)),
        now=NOW,
    )
    # Le vrai téléphone peut toujours renouveler : un voleur sans la clé ne
    # peut pas couper la session de quelqu'un.
    assert refresh(db, phone, tokens)


def test_a_login_signature_cannot_be_reused_to_refresh(db):
    phone = Phone()
    tokens = sign_in(db, phone)

    refused("invalid_signature", app_sessions.refresh, db, refresh_token=tokens.refresh_token,
            signature=phone.sign(app_sessions.login_message(tokens.refresh_token)), now=NOW)


def test_reusing_an_old_refresh_token_cuts_the_whole_family(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    renewed = refresh(db, phone, tokens, now=NOW + timedelta(minutes=20))

    refused("unauthorized", refresh, db, phone, tokens, now=NOW + timedelta(minutes=21))

    refused("unauthorized", app_sessions.authenticate, db, renewed.access_token, now=NOW + timedelta(minutes=21))
    refused("unauthorized", refresh, db, phone, renewed, now=NOW + timedelta(minutes=22))
    assert db.query(models.AuthEvent).filter_by(result="token_reuse").count() == 1


def test_an_expired_refresh_token_is_refused(db):
    phone = Phone()
    tokens = sign_in(db, phone)

    refused("unauthorized", refresh, db, phone, tokens, now=NOW + timedelta(days=30))


def test_an_unknown_refresh_token_is_refused(db):
    phone = Phone()
    sign_in(db, phone)

    refused("unauthorized", app_sessions.refresh, db, refresh_token="inconnu",
            signature=phone.sign(app_sessions.refresh_message("inconnu")), now=NOW)


# --- Déconnexion et coupure ---------------------------------------------------


def test_signing_out_cuts_the_session_but_keeps_the_device(db):
    phone = Phone()
    tokens = sign_in(db, phone)

    app_sessions.sign_out(db, app_sessions.authenticate(db, tokens.access_token, now=NOW), now=NOW)

    refused("unauthorized", app_sessions.authenticate, db, tokens.access_token, now=NOW)
    refused("unauthorized", refresh, db, phone, tokens)
    assert device(db, tokens).revoked_at is None


def test_revoking_a_lost_phone_from_another_phone_cuts_it_at_once(db):
    lost, kept = Phone(), Phone()
    lost_tokens = sign_in(db, lost)
    kept_tokens = sign_in(db, kept, now=NOW + timedelta(minutes=1))
    principal = app_sessions.authenticate(db, kept_tokens.access_token, now=NOW + timedelta(minutes=2))

    app_sessions.revoke_own_device(db, principal, lost_tokens.device_id, now=NOW + timedelta(minutes=2))

    refused("unauthorized", app_sessions.authenticate, db, lost_tokens.access_token, now=NOW + timedelta(minutes=3))
    refused("unauthorized", refresh, db, lost, lost_tokens, now=NOW + timedelta(minutes=3))
    assert device(db, lost_tokens).revoked_reason == "revoked_by_owner"
    assert app_sessions.authenticate(db, kept_tokens.access_token, now=NOW + timedelta(minutes=3))


def test_nobody_can_revoke_a_phone_of_another_account(db):
    mine = sign_in(db, Phone(), telegram_id=601)
    other_phone = Phone()
    public_id, code = code_for(db, other_phone, telegram_id=602, number="+243810000002")
    theirs = app_sessions.sign_in(
        db,
        challenge_public_id=public_id,
        code=code,
        public_key=other_phone.public_key,
        signature=other_phone.sign(app_sessions.login_message(public_id)),
        platform="ios",
        app_version="1.0.0",
        now=NOW,
    )
    principal = app_sessions.authenticate(db, mine.access_token, now=NOW)

    refused("device_not_found", app_sessions.revoke_own_device, db, principal, theirs.device_id, now=NOW)

    assert device(db, theirs).revoked_at is None


def test_the_device_list_shows_only_my_phones(db):
    mine = sign_in(db, Phone(), telegram_id=601)
    other_phone = Phone()
    public_id, code = code_for(db, other_phone, telegram_id=602, number="+243810000002")
    app_sessions.sign_in(
        db, challenge_public_id=public_id, code=code, public_key=other_phone.public_key,
        signature=other_phone.sign(app_sessions.login_message(public_id)), platform="ios", app_version="1.0.0", now=NOW,
    )

    assert [d.id for d in app_sessions.list_devices(db, mine.account_id)] == [mine.device_id]


def test_revoking_all_devices_cuts_every_phone_and_session(db):
    first = sign_in(db, Phone())
    second = sign_in(db, Phone(), now=NOW + timedelta(minutes=1))

    assert app_sessions.revoke_all_devices(db, first.account_id, now=NOW + timedelta(minutes=2)) == 2

    for tokens in (first, second):
        refused("unauthorized", app_sessions.authenticate, db, tokens.access_token, now=NOW + timedelta(minutes=3))
        assert device(db, tokens).revoked_reason == "revoked_by_admin"
    assert db.query(models.AppSession).filter(models.AppSession.revoked_at.is_(None)).count() == 0


def test_revoking_devices_never_touches_money(db):
    tokens = sign_in(db, Phone())
    ledger.record_opening_balance(db, tokens.account_id, "USD", 25)
    db.commit()

    app_sessions.revoke_all_devices(db, tokens.account_id, now=NOW)

    assert ledger.wallet_balances(db, tokens.account_id)["USD"] == 25


# --- Route admin du bot -------------------------------------------------------

TEST_API_KEY = "test-backend-api-key-not-a-secret"


@pytest.fixture
def backend(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'route.db'}")
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TEST_API_KEY)
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "999")
    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    database_module.init_db()
    client = TestClient(backend_main.app)
    client.headers["X-API-Key"] = TEST_API_KEY
    return client, database_module


def _as(telegram_id):
    return {"X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def test_the_admin_cuts_all_phones_of_a_person(backend):
    client, database = backend
    with database.SessionLocal() as session:
        tokens = sign_in(session, Phone(), telegram_id=601)

    response = client.post("/api/bot/admin/app-devices/revoke", json={"telegram_id": 601}, headers=_as(999))

    assert response.status_code == 200 and response.json()["revoked"] == 1
    with database.SessionLocal() as session:
        assert session.get(models.Device, tokens.device_id).revoked_reason == "revoked_by_admin"


def test_only_the_admin_can_cut_phones(backend):
    client, database = backend
    with database.SessionLocal() as session:
        tokens = sign_in(session, Phone(), telegram_id=601)

    response = client.post("/api/bot/admin/app-devices/revoke", json={"telegram_id": 601}, headers=_as(601))

    assert response.status_code == 403
    with database.SessionLocal() as session:
        assert session.get(models.Device, tokens.device_id).revoked_at is None


def test_cutting_phones_of_an_unknown_person_says_so(backend):
    client, _ = backend

    response = client.post("/api/bot/admin/app-devices/revoke", json={"telegram_id": 12345}, headers=_as(999))

    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "account_not_found"}
