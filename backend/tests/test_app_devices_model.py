"""Application mobile, étape 1, PR 1 : modèle des appareils, sessions, codes
de connexion, nonces et journal (app-mobile/plan-etape1-connexion-api).

Ces tests prouvent que la base elle-même refuse les états impossibles, quel
que soit le code qui écrit : clé d'appareil en double, appareil coupé sans
raison, jeton en double, rotation qui pointe deux fois vers la même session,
code consommé sans code, essais au-delà de la limite, nonce rejoué, seconde
identité `app` pour un même compte.

Les mêmes contraintes sont vérifiées sur Postgres par la migration
(`test_app_devices_migration.py`).
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app import ledger, models

NOW = datetime(2026, 11, 7, 8, 0, 0)


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def account_id(db):
    account = models.NexisAccount()
    db.add(account)
    db.commit()
    return account.id


def device(account_id, **overrides):
    values = dict(
        account_id=account_id,
        platform="android",
        public_key="MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE",
        key_thumbprint="a" * 64,
        attestation="verified",
        label="Samsung A54",
        app_version="1.0.0",
        created_at=NOW,
        money_unlocked_at=NOW + timedelta(hours=72),
    )
    values.update(overrides)
    return models.Device(**values)


def session_row(device_id, **overrides):
    values = dict(
        device_id=device_id,
        family_id="f" * 32,
        access_hash="1" * 64,
        access_expires_at=NOW + timedelta(minutes=15),
        refresh_hash="2" * 64,
        refresh_expires_at=NOW + timedelta(days=30),
        created_at=NOW,
    )
    values.update(overrides)
    return models.AppSession(**values)


def challenge(**overrides):
    values = dict(
        public_id="p" * 32,
        phone_e164="+243810000001",
        purpose="signup",
        delivery="telegram",
        device_key_thumbprint="a" * 64,
        created_at=NOW,
        expires_at=NOW + timedelta(minutes=10),
    )
    values.update(overrides)
    return models.LoginChallenge(**values)


def refused(db, row):
    db.add(row)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def saved(db, row):
    db.add(row)
    db.commit()
    return row


# --- Appareils ---------------------------------------------------------------


def test_a_device_is_saved_with_its_key_and_money_delay(db, account_id):
    row = saved(db, device(account_id))

    assert row.id is not None
    assert row.revoked_at is None
    assert row.money_unlocked_at - row.created_at == timedelta(hours=72)


def test_the_same_device_key_cannot_belong_to_two_devices(db, account_id):
    saved(db, device(account_id))

    refused(db, device(account_id, public_key="autre"))


@pytest.mark.parametrize("platform", ["windows", "", "Android"])
def test_only_android_and_ios_devices_exist(db, account_id, platform):
    refused(db, device(account_id, platform=platform))


def test_ios_devices_are_accepted(db, account_id):
    assert saved(db, device(account_id, platform="ios")).platform == "ios"


@pytest.mark.parametrize("attestation", ["maybe", "", "VERIFIED"])
def test_attestation_is_verified_or_unverified_and_nothing_else(db, account_id, attestation):
    refused(db, device(account_id, attestation=attestation))


def test_an_unverified_device_can_exist(db, account_id):
    assert saved(db, device(account_id, attestation="unverified")).attestation == "unverified"


def test_a_device_cannot_be_revoked_without_a_reason(db, account_id):
    refused(db, device(account_id, revoked_at=NOW))


def test_a_reason_without_revocation_is_refused(db, account_id):
    refused(db, device(account_id, revoked_reason="lost_phone"))


def test_a_revoked_device_keeps_its_date_and_reason(db, account_id):
    row = saved(db, device(account_id, revoked_at=NOW, revoked_reason="lost_phone"))

    assert (row.revoked_at, row.revoked_reason) == (NOW, "lost_phone")


def test_money_cannot_be_unlocked_before_the_device_exists(db, account_id):
    refused(db, device(account_id, money_unlocked_at=NOW - timedelta(seconds=1)))


# --- Sessions ----------------------------------------------------------------


def test_a_session_is_saved_with_hashed_tokens(db, account_id):
    phone = saved(db, device(account_id))

    row = saved(db, session_row(phone.id))

    assert len(row.access_hash) == 64 and len(row.refresh_hash) == 64


def test_two_sessions_cannot_share_an_access_token(db, account_id):
    phone = saved(db, device(account_id))
    saved(db, session_row(phone.id))

    refused(db, session_row(phone.id, refresh_hash="3" * 64))


def test_two_sessions_cannot_share_a_refresh_token(db, account_id):
    phone = saved(db, device(account_id))
    saved(db, session_row(phone.id))

    refused(db, session_row(phone.id, access_hash="4" * 64))


def test_a_rotated_session_points_to_its_single_successor(db, account_id):
    phone = saved(db, device(account_id))
    first = saved(db, session_row(phone.id))
    second = saved(db, session_row(phone.id, access_hash="5" * 64, refresh_hash="6" * 64))
    first.replaced_by_id = second.id
    db.commit()

    third = session_row(phone.id, access_hash="7" * 64, refresh_hash="8" * 64, replaced_by_id=second.id)

    refused(db, third)


def test_an_access_token_must_expire_after_its_creation(db, account_id):
    phone = saved(db, device(account_id))

    refused(db, session_row(phone.id, access_expires_at=NOW))


def test_a_refresh_token_cannot_expire_before_the_access_token(db, account_id):
    phone = saved(db, device(account_id))

    refused(db, session_row(phone.id, refresh_expires_at=NOW + timedelta(minutes=1)))


def test_a_session_cannot_be_revoked_without_a_reason(db, account_id):
    phone = saved(db, device(account_id))

    refused(db, session_row(phone.id, revoked_at=NOW))


# --- Codes de connexion ------------------------------------------------------


def test_a_challenge_starts_with_no_attempt_and_no_code(db):
    row = saved(db, challenge())

    assert row.attempts == 0
    assert row.code_hash is None and row.consumed_at is None


def test_challenge_public_ids_are_unique(db):
    saved(db, challenge())

    refused(db, challenge(phone_e164="+243810000002"))


def test_a_telegram_start_link_is_single_use(db):
    saved(db, challenge(telegram_start_hash="t" * 64))

    refused(db, challenge(public_id="q" * 32, telegram_start_hash="t" * 64))


@pytest.mark.parametrize("attempts", [-1, models.MAX_CODE_ATTEMPTS + 1])
def test_attempts_stay_between_zero_and_the_limit(db, attempts):
    refused(db, challenge(attempts=attempts))


def test_the_last_allowed_attempt_is_accepted(db):
    assert saved(db, challenge(attempts=models.MAX_CODE_ATTEMPTS)).attempts == models.MAX_CODE_ATTEMPTS


def test_a_challenge_cannot_be_consumed_before_a_code_was_sent(db):
    refused(db, challenge(consumed_at=NOW))


def test_a_challenge_with_a_code_can_be_consumed(db):
    row = saved(db, challenge(code_hash="c" * 64, consumed_at=NOW))

    assert row.consumed_at == NOW


@pytest.mark.parametrize("field,value", [("purpose", "reset"), ("delivery", "sms"), ("delivery", "email")])
def test_unknown_purposes_and_deliveries_are_refused(db, field, value):
    refused(db, challenge(**{field: value}))


def test_a_challenge_must_expire_after_its_creation(db):
    refused(db, challenge(expires_at=NOW))


# --- Nonces et journal -------------------------------------------------------


def test_a_nonce_cannot_be_seen_twice_for_the_same_device(db, account_id):
    phone = saved(db, device(account_id))
    saved(db, models.RequestNonce(device_id=phone.id, nonce="n1", seen_at=NOW))

    refused(db, models.RequestNonce(device_id=phone.id, nonce="n1", seen_at=NOW))


def test_two_devices_may_use_the_same_nonce_value(db, account_id):
    first = saved(db, device(account_id))
    second = saved(db, device(account_id, key_thumbprint="b" * 64))
    saved(db, models.RequestNonce(device_id=first.id, nonce="n1", seen_at=NOW))

    assert saved(db, models.RequestNonce(device_id=second.id, nonce="n1", seen_at=NOW)).id is not None


def test_an_auth_event_can_be_recorded_without_account_or_device(db):
    row = saved(db, models.AuthEvent(type="challenge_requested", result="accepted", created_at=NOW))

    assert row.account_id is None and row.device_id is None


# --- Identité `app` ----------------------------------------------------------


def test_an_account_has_at_most_one_app_identity(db, account_id):
    saved(db, models.ChannelIdentity(account_id=account_id, channel=ledger.APP, external_id="x" * 32, verified_at=NOW))

    refused(db, models.ChannelIdentity(account_id=account_id, channel=ledger.APP, external_id="y" * 32, verified_at=NOW))


def test_an_app_identity_resolves_to_its_account(db, account_id):
    saved(db, models.ChannelIdentity(account_id=account_id, channel=ledger.APP, external_id="x" * 32, verified_at=NOW))

    assert ledger.account_id_for(db, ledger.APP, "x" * 32) == account_id
