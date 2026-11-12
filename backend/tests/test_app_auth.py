"""Codes de connexion de l'application mobile (étape 1, PR 2) : tests
d'attaque et cas normaux de `backend/app/app_auth.py`, du numéro prouvé à
l'inscription Telegram, et de la route du bot `/api/bot/app-login/telegram-contact`.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5.1 à 5.4.
"""

import importlib
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app_auth, crud, ledger, models

NOW = datetime(2026, 11, 7, 8, 0, 0)
DEVICE = "a" * 64
OTHER_DEVICE = "b" * 64
PHONE = "+243810000001"
HMAC_KEY = "test-hmac-key-not-a-secret-0123456789abcdef"


@pytest.fixture(autouse=True)
def code_key(monkeypatch):
    monkeypatch.setenv("APP_CODE_HMAC_KEY", HMAC_KEY)


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def refused(expected, call, *args, **kwargs):
    with pytest.raises(app_auth.AuthError) as error:
        call(*args, **kwargs)
    assert error.value.code == expected
    return error.value


def challenge(db, phone=PHONE, device=DEVICE, now=NOW, **kwargs):
    return app_auth.create_challenge(db, phone=phone, delivery="telegram", device_key_thumbprint=device, now=now, **kwargs)


def telegram_code(db, created, telegram_id=601, phone=PHONE, now=NOW):
    return app_auth.issue_code_for_telegram_contact(
        db, start_token=created.telegram_start_token, telegram_id=telegram_id, contact_phone=phone, now=now
    )


def verify(db, created, code, device=DEVICE, now=NOW):
    return app_auth.verify_code(db, public_id=created.public_id, code=code, device_key_thumbprint=device, now=now)


def stored(db, created):
    return db.query(models.LoginChallenge).filter_by(public_id=created.public_id).one()


def account_of_telegram(db, telegram_id):
    return db.get(models.NexisAccount, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id))


def prove(db, telegram_id, phone):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    assert app_auth.prove_phone(db, account_id, phone, now=NOW)
    db.commit()
    return account_id


# --- Numéros ------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+243810000001", "+243810000001"),
        ("243810000001", "+243810000001"),  # Telegram envoie parfois sans +
        ("00243810000001", "+243810000001"),
        ("+243 81 000 0001", "+243810000001"),
        ("+33 6 12 34 56 78", "+33612345678"),
    ],
)
def test_phone_numbers_are_normalized(raw, expected):
    assert app_auth.normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", None, "+0123456789", "081000", "+243abc", "+2438100000011234567"])
def test_unreadable_phone_numbers_are_refused(raw):
    refused("invalid_phone", app_auth.normalize_phone, raw)


# --- Demande de code ----------------------------------------------------------


def test_without_a_strong_hmac_key_no_challenge_is_created(db, monkeypatch):
    monkeypatch.setenv("APP_CODE_HMAC_KEY", "court")

    refused("auth_not_configured", challenge, db)
    assert db.query(models.LoginChallenge).count() == 0


def test_whatsapp_codes_are_refused_until_the_whatsapp_sender_exists(db):
    refused(
        "delivery_unavailable",
        app_auth.create_challenge,
        db,
        phone=PHONE,
        delivery="whatsapp",
        device_key_thumbprint=DEVICE,
        now=NOW,
    )
    assert db.query(models.LoginChallenge).count() == 0


def test_unknown_deliveries_are_refused(db):
    refused("invalid_delivery", app_auth.create_challenge, db, phone=PHONE, delivery="sms", device_key_thumbprint=DEVICE)


def test_a_malformed_device_key_is_refused(db):
    refused("invalid_device_key", challenge, db, device="pas-une-empreinte")


def test_an_unknown_number_gives_a_signup_challenge_with_a_start_link(db):
    created = challenge(db)

    row = stored(db, created)
    assert (row.purpose, row.account_id, row.code_hash) == ("signup", None, None)
    assert created.telegram_start_token and len(created.telegram_start_token) == 32
    assert row.telegram_start_hash != created.telegram_start_token  # jamais en clair
    assert created.expires_at == NOW + timedelta(minutes=10)
    assert len(app_auth.telegram_start_payload(created.telegram_start_token)) <= 64


def test_a_proven_number_gives_a_login_challenge_for_its_account(db):
    account_id = prove(db, 601, PHONE)

    created = challenge(db)

    row = stored(db, created)
    assert (row.purpose, row.account_id) == ("login", account_id)


def test_the_response_does_not_reveal_whether_a_number_is_known(db):
    prove(db, 601, PHONE)

    known = challenge(db, device="c" * 64)
    unknown = challenge(db, phone="+243810000002", device="d" * 64)

    assert set(vars(known)) == set(vars(unknown))
    assert known.delivery == unknown.delivery == "telegram"


def test_a_fourth_request_in_the_same_hour_for_a_number_is_refused(db):
    for minute in range(app_auth.PHONE_PER_HOUR):
        challenge(db, device=f"{minute:064x}", now=NOW + timedelta(minutes=minute))

    error = refused("rate_limited", challenge, db, device="e" * 64, now=NOW + timedelta(minutes=10))

    assert error.http_status == 429
    assert db.query(models.AuthEvent).filter_by(result="rate_limited").count() == 1


def test_the_hourly_limit_frees_up_after_an_hour(db):
    for minute in range(app_auth.PHONE_PER_HOUR):
        challenge(db, device=f"{minute:064x}", now=NOW + timedelta(minutes=minute))

    assert challenge(db, device="e" * 64, now=NOW + timedelta(hours=1, minutes=3))


def test_a_number_gets_at_most_ten_requests_a_day(db):
    for index in range(app_auth.PHONE_PER_DAY):
        challenge(db, device=f"{index:064x}", now=NOW + timedelta(hours=2 * index))

    refused("rate_limited", challenge, db, device="e" * 64, now=NOW + timedelta(hours=20, minutes=30))


def test_one_device_cannot_spray_requests_over_many_numbers(db):
    for index in range(app_auth.DEVICE_PER_HOUR):
        challenge(db, phone=f"+24381000010{index}", now=NOW + timedelta(minutes=index))

    refused("rate_limited", challenge, db, phone="+243810000199", now=NOW + timedelta(minutes=30))


def test_one_network_address_is_limited_too(db):
    for index in range(app_auth.IP_PER_HOUR):
        challenge(db, phone=f"+2438100002{index:02d}", device=f"{index:064x}", ip_hash="i" * 64, now=NOW)

    refused("rate_limited", challenge, db, phone="+243810000299", device="f" * 64, ip_hash="i" * 64, now=NOW)


# --- Code par Telegram --------------------------------------------------------


def test_a_new_telegram_user_gets_a_new_account_with_the_proven_number(db):
    created = challenge(db)

    issued = telegram_code(db, created, telegram_id=601)

    account = account_of_telegram(db, 601)
    assert account is not None
    assert (account.phone_e164, account.phone_verified_at) == (PHONE, NOW)
    row = stored(db, created)
    assert (row.account_id, row.purpose) == (account.id, "signup")
    assert len(issued.code) == 6 and issued.code.isdigit()


def test_the_code_is_never_stored_in_clear(db):
    created = challenge(db)
    issued = telegram_code(db, created)

    row = stored(db, created)
    assert issued.code not in (row.code_hash or "")
    assert row.code_hash != issued.code


def test_an_existing_telegram_account_gets_the_app_on_the_same_account(db):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, 601, create=True)
    db.commit()
    created = challenge(db)

    telegram_code(db, created, telegram_id=601)

    row = stored(db, created)
    assert (row.account_id, row.purpose) == (account_id, "login")
    assert db.get(models.NexisAccount, account_id).phone_e164 == PHONE


def test_a_proven_number_gets_its_code_only_on_its_own_telegram(db):
    owner = prove(db, 601, PHONE)
    created = challenge(db)

    refused("phone_conflict", telegram_code, db, created, telegram_id=602)

    assert stored(db, created).code_hash is None
    assert db.get(models.NexisAccount, owner).phone_e164 == PHONE
    assert ledger.account_id_for(db, ledger.TELEGRAM, 602) is None
    assert db.query(models.AuthEvent).filter_by(result="phone_conflict").count() == 1


def test_the_owner_of_a_proven_number_gets_the_code(db):
    owner = prove(db, 601, PHONE)
    created = challenge(db)

    telegram_code(db, created, telegram_id=601)

    assert (stored(db, created).account_id, stored(db, created).purpose) == (owner, "login")


def test_a_shared_number_different_from_the_typed_one_is_refused(db):
    created = challenge(db)

    refused("phone_mismatch", telegram_code, db, created, phone="+243810000999")

    assert stored(db, created).code_hash is None
    assert ledger.account_id_for(db, ledger.TELEGRAM, 601) is None


def test_the_number_shared_without_plus_matches_the_typed_one(db):
    created = challenge(db)

    assert telegram_code(db, created, phone="243810000001").code


def test_a_start_link_gives_only_one_code(db):
    created = challenge(db)
    telegram_code(db, created)

    refused("link_invalid", telegram_code, db, created)


def test_an_expired_start_link_is_refused(db):
    created = challenge(db)

    refused("link_invalid", telegram_code, db, created, now=NOW + timedelta(minutes=10))


@pytest.mark.parametrize("token", ["", "x" * 32, "court", "a" * 31 + "!"])
def test_unknown_or_malformed_start_links_are_refused(db, token):
    challenge(db)

    refused(
        "link_invalid",
        app_auth.issue_code_for_telegram_contact,
        db,
        start_token=token,
        telegram_id=601,
        contact_phone=PHONE,
        now=NOW,
    )


# --- Vérification du code -----------------------------------------------------


def test_the_right_code_on_the_right_device_opens_the_account_once(db):
    created = challenge(db)
    issued = telegram_code(db, created)

    verified = verify(db, created, issued.code)

    assert verified.account_id == account_of_telegram(db, 601).id
    assert verified.existing_account is False
    refused("invalid_code", verify, db, created, issued.code)


def test_an_existing_account_is_flagged_for_the_money_delay(db):
    prove(db, 601, PHONE)
    created = challenge(db)
    issued = telegram_code(db, created)

    assert verify(db, created, issued.code).existing_account is True


def test_a_wrong_code_counts_an_attempt(db):
    created = challenge(db)
    issued = telegram_code(db, created)
    wrong = f"{(int(issued.code) + 1) % 1_000_000:06d}"

    refused("invalid_code", verify, db, created, wrong)

    assert stored(db, created).attempts == 1


def test_the_fifth_wrong_code_kills_the_challenge_even_for_the_right_code(db):
    created = challenge(db)
    issued = telegram_code(db, created)
    wrong = f"{(int(issued.code) + 1) % 1_000_000:06d}"
    for _ in range(models.MAX_CODE_ATTEMPTS - 1):
        refused("invalid_code", verify, db, created, wrong)

    refused("too_many_attempts", verify, db, created, wrong)
    refused("too_many_attempts", verify, db, created, issued.code)

    assert stored(db, created).consumed_at is None


def test_a_code_does_not_work_on_another_device(db):
    created = challenge(db)
    issued = telegram_code(db, created)

    refused("invalid_code", verify, db, created, issued.code, device=OTHER_DEVICE)

    assert stored(db, created).attempts == 1


def test_an_expired_code_is_refused(db):
    created = challenge(db)
    issued = telegram_code(db, created)

    refused("code_expired", verify, db, created, issued.code, now=NOW + timedelta(minutes=10))


def test_no_code_works_before_one_was_issued(db):
    created = challenge(db)

    refused("invalid_code", verify, db, created, "000000")


def test_an_unknown_challenge_gives_the_same_answer_as_a_wrong_code(db):
    refused("invalid_code", app_auth.verify_code, db, public_id="0" * 32, code="123456", device_key_thumbprint=DEVICE, now=NOW)


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", ""])
def test_malformed_codes_are_wrong_codes(db, code):
    created = challenge(db)
    telegram_code(db, created)

    refused("invalid_code", verify, db, created, code)


# --- Numéro prouvé ------------------------------------------------------------


def test_a_number_proven_on_one_account_never_moves_to_another(db):
    owner = prove(db, 601, PHONE)
    other = ledger.account_id_for(db, ledger.TELEGRAM, 602, create=True)

    assert app_auth.prove_phone(db, other, PHONE, now=NOW) is False
    db.commit()

    assert db.get(models.NexisAccount, owner).phone_e164 == PHONE
    assert db.get(models.NexisAccount, other).phone_e164 is None


def test_a_new_proven_number_replaces_the_old_one_on_the_same_account(db):
    account_id = prove(db, 601, PHONE)

    assert app_auth.prove_phone(db, account_id, "+243810000002", now=NOW + timedelta(days=1))
    db.commit()

    assert db.get(models.NexisAccount, account_id).phone_e164 == "+243810000002"
    assert db.query(models.AuthEvent).filter_by(type="phone_changed").count() == 1


def test_telegram_registration_with_a_shared_number_proves_it(db):
    crud.upsert_user(db, 601, "Ben", "243810000001", language="fr", phone_verified=True)

    account = account_of_telegram(db, 601)
    assert account.phone_e164 == PHONE and account.phone_verified_at is not None


def test_a_number_not_flagged_as_shared_is_never_proven(db):
    crud.upsert_user(db, 601, "Ben", PHONE, language="fr")

    assert account_of_telegram(db, 601).phone_e164 is None


def test_provider_registration_with_a_shared_number_proves_it(db):
    crud.upsert_provider(db, 601, "Ben", PHONE, ["service_plomberie"], ["Gombe"], phone_verified=True)

    assert account_of_telegram(db, 601).phone_e164 == PHONE


def test_registration_still_works_when_the_number_belongs_to_another_account(db):
    prove(db, 601, PHONE)

    user = crud.upsert_user(db, 602, "Autre", PHONE, language="fr", phone_verified=True)

    assert user.telegram_id == 602
    assert account_of_telegram(db, 602).phone_e164 is None
    assert account_of_telegram(db, 601).phone_e164 == PHONE


# --- Route du bot -------------------------------------------------------------

TEST_API_KEY = "test-backend-api-key-not-a-secret"


@pytest.fixture
def backend(monkeypatch, backend_db_url):
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TEST_API_KEY)
    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    database_module.init_db()
    client = TestClient(backend_main.app)
    client.headers["X-API-Key"] = TEST_API_KEY
    return client, database_module, importlib.import_module("backend.app.app_auth")


def _as(telegram_id):
    return {"X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def test_the_bot_route_returns_the_code_for_the_sender(backend):
    client, database, auth = backend
    with database.SessionLocal() as session:
        created = auth.create_challenge(session, phone=PHONE, delivery="telegram", device_key_thumbprint=DEVICE)

    response = client.post(
        "/api/bot/app-login/telegram-contact",
        json={"start_token": created.telegram_start_token, "phone": PHONE},
        headers=_as(601),
    )

    assert response.status_code == 200
    assert len(response.json()["code"]) == 6


def test_the_bot_route_refuses_with_a_stable_code(backend):
    client, _, _ = backend

    response = client.post(
        "/api/bot/app-login/telegram-contact", json={"start_token": "x" * 32, "phone": PHONE}, headers=_as(601)
    )

    assert response.status_code == 400
    assert response.json()["detail"] == {"code": "link_invalid"}


def test_the_bot_route_needs_the_service_key_and_the_actor(backend):
    client, _, _ = backend
    body = {"start_token": "x" * 32, "phone": PHONE}

    assert client.post("/api/bot/app-login/telegram-contact", json=body).status_code == 400
    assert client.post("/api/bot/app-login/telegram-contact", json=body, headers={**_as(601), "X-API-Key": "faux"}).status_code == 401
