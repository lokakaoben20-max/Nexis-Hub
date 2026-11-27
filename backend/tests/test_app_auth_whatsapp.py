"""Connexion à l'application par WhatsApp (étape 8 du plan WhatsApp, seconde
partie ; plan de l'app, sections 5.1, 5.3 et 5.4), contre le faux Meta.

Parcours : l'app ouvre la conversation WhatsApp de NexisHub avec un message
déjà écrit qui porte un jeton (jamais le code) ; la personne l'envoie ; le
backend vérifie le jeton, l'identité qui écrit et le numéro donné par Meta,
puis envoie lui-même le code à cette identité.

Ce qui est vérifié : le code ne part qu'à l'identité qui écrit, et seulement
si son numéro est celui tapé dans l'app et n'est pas prouvé par un autre
compte (numéro réattribué) ; numéro masqué refusé ; jeton à usage unique, du
bon canal ; le code n'est ni dans la réponse au service, ni dans la réponse
gardée pour un message rejoué, ni en base ; renvoi après 60 s ; 5 codes faux
par numéro, tous canaux confondus, bloquent 15 minutes.
"""

import importlib
import re
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import app_auth, crud, ledger, models
from whatsapp_bot.fake_meta import FakeMeta

NOW = datetime.utcnow().replace(microsecond=0)
DEVICE = "a" * 64
PHONE = "+243810000009"
BSUID = "CD.7000000000000000007"
OTHER_BSUID = "CD.7000000000000000008"
HMAC_KEY = "test-hmac-key-not-a-secret-0123456789abcdef"
ACCESS_TOKEN = "test-access-token-not-a-secret"
PHONE_NUMBER_ID = "100000000000001"
WHATSAPP_KEY = "test-whatsapp-key-not-a-secret-0123456789"
TELEGRAM_KEY = "test-backend-api-key-not-a-secret"


def configure(monkeypatch):
    monkeypatch.setenv("APP_CODE_HMAC_KEY", HMAC_KEY)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", ACCESS_TOKEN)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    monkeypatch.setenv("WHATSAPP_GRAPH_URL", "https://graph.facebook.test/v23.0")
    monkeypatch.setenv("WHATSAPP_CALLBACK_KEY", "test-callback-key-not-a-secret-0000000001")
    monkeypatch.setenv(app_auth.WHATSAPP_NUMBER_ENV, "243990000000")


def fake_meta(monkeypatch):
    from backend.app import notify_whatsapp

    meta = FakeMeta(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID, app_secret="secret-not-used")
    api = TestClient(meta.app())
    monkeypatch.setattr(notify_whatsapp, "_http_post", lambda url, json, headers, timeout: api.post(url, json=json, headers=headers))
    return meta


@pytest.fixture
def db(backend_db_url, monkeypatch):
    configure(monkeypatch)
    engine = create_engine(backend_db_url, future=True)
    models.Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    yield session
    session.close()
    engine.dispose()


def ask(db, phone=PHONE, device=DEVICE, now=NOW, delivery="whatsapp"):
    return app_auth.create_challenge(db, phone=phone, delivery=delivery, device_key_thumbprint=device, now=now)


def write(db, created, bsuid=BSUID, phone=PHONE, now=NOW):
    """La personne envoie le message préparé ; Meta donne son identité et son numéro."""
    return app_auth.issue_code_for_whatsapp(db, start_token=created.start_token, bsuid=bsuid, phone=phone, now=now)


def verify(db, created, code, device=DEVICE, now=NOW):
    return app_auth.verify_code(db, public_id=created.public_id, code=code, device_key_thumbprint=device, now=now)


def refused(call):
    with pytest.raises(app_auth.AuthError) as error:
        call()
    return error.value


def whatsapp_client(db, phone=PHONE, bsuid=BSUID):
    account, _ = crud.register_whatsapp_client(db, bsuid=bsuid, display_name="Mado", language="en", phone=phone)
    db.commit()
    return account.id


# --- Règles (app_auth) ----------------------------------------------------------------


def test_whatsapp_is_offered_only_when_the_backend_can_answer_and_knows_the_number(db, monkeypatch):
    assert app_auth.available_deliveries() == ("telegram", "whatsapp")
    monkeypatch.setenv(app_auth.WHATSAPP_NUMBER_ENV, "pas-un-numero")
    assert app_auth.available_deliveries() == ("telegram",)
    monkeypatch.setenv(app_auth.WHATSAPP_NUMBER_ENV, "243990000000")
    monkeypatch.delenv("WHATSAPP_CALLBACK_KEY")
    assert app_auth.available_deliveries() == ("telegram",)


def test_a_new_person_writing_from_the_link_gets_an_account_its_whatsapp_and_its_number(db):
    created = ask(db)
    challenge = db.query(models.LoginChallenge).one()
    assert challenge.code_hash is None and challenge.telegram_start_hash != created.start_token

    issued = write(db, created)
    account_id = ledger.account_id_for(db, ledger.WHATSAPP, BSUID)
    account = db.get(models.NexisAccount, account_id)
    assert account.phone_e164 == PHONE and account.phone_verified_at is not None
    db.refresh(challenge)
    assert issued.code not in challenge.code_hash

    verified = verify(db, created, issued.code)
    assert verified.account_id == account_id and verified.existing_account is False
    # Usage unique, et le jeton aussi.
    assert refused(lambda: verify(db, created, issued.code)).code == "invalid_code"
    assert refused(lambda: write(db, created)).code == "link_invalid"


def test_a_known_whatsapp_client_signs_in_to_its_own_account(db):
    account_id = whatsapp_client(db)
    created = ask(db)
    issued = write(db, created)
    verified = verify(db, created, issued.code)
    assert verified.account_id == account_id and verified.existing_account is True


def test_a_reassigned_number_does_not_open_the_former_owners_account(db):
    """Le numéro est prouvé par le compte de BSUID ; un autre WhatsApp (nouveau
    titulaire du numéro chez l'opérateur) écrit depuis le lien : refus."""
    whatsapp_client(db)
    created = ask(db)
    assert refused(lambda: write(db, created, bsuid=OTHER_BSUID)).code == "phone_conflict"
    assert db.query(models.LoginChallenge).one().code_hash is None
    assert ledger.account_id_for(db, ledger.WHATSAPP, OTHER_BSUID) is None


def test_a_number_proven_by_a_telegram_account_is_never_taken_from_whatsapp(db):
    telegram_account = ledger.account_id_for(db, ledger.TELEGRAM, 601, create=True)
    assert app_auth.prove_phone(db, telegram_account, PHONE, now=NOW)
    db.commit()
    created = ask(db)
    assert refused(lambda: write(db, created)).code == "phone_conflict"


def test_another_number_than_the_one_typed_or_a_hidden_number_proves_nothing(db):
    created = ask(db)
    assert refused(lambda: write(db, created, phone="+243810000077")).code == "phone_mismatch"
    assert refused(lambda: write(db, created, phone=None)).code == "phone_hidden"
    assert db.query(models.LoginChallenge).one().code_hash is None
    assert db.query(models.NexisAccount).count() == 0


def test_a_telegram_link_cannot_be_used_on_whatsapp_and_the_other_way_round(db):
    by_telegram = ask(db, delivery="telegram")
    assert refused(lambda: write(db, by_telegram)).code == "link_invalid"
    by_whatsapp = ask(db, phone="+243810000010")
    error = refused(
        lambda: app_auth.issue_code_for_telegram_contact(
            db, start_token=by_whatsapp.start_token, telegram_id=601, contact_phone="+243810000010", now=NOW
        )
    )
    assert error.code == "link_invalid"


def test_an_expired_link_gives_no_code(db):
    created = ask(db)
    assert refused(lambda: write(db, created, now=NOW + timedelta(minutes=10))).code == "link_invalid"


def test_the_code_is_bound_to_the_device_that_asked(db):
    created = ask(db)
    issued = write(db, created)
    assert refused(lambda: verify(db, created, issued.code, device="b" * 64)).code == "invalid_code"


def test_a_new_request_waits_60_seconds_then_the_hourly_limit_applies(db):
    ask(db)
    assert refused(lambda: ask(db, now=NOW + timedelta(seconds=59))).code == "rate_limited"
    ask(db, now=NOW + timedelta(seconds=61))
    ask(db, now=NOW + timedelta(seconds=122))
    assert refused(lambda: ask(db, now=NOW + timedelta(seconds=183))).code == "rate_limited"


def test_five_wrong_codes_on_a_number_lock_it_15_minutes_across_requests_and_channels(db, monkeypatch):
    monkeypatch.setattr(app_auth, "PHONE_PER_HOUR", 10)

    def by_telegram(now):
        created = ask(db, delivery="telegram", now=now)
        issued = app_auth.issue_code_for_telegram_contact(
            db, start_token=created.start_token, telegram_id=601, contact_phone=PHONE, now=now
        )
        return created, issued.code

    # Codes faux sur deux demandes par Telegram : ils comptent ensemble.
    first, _code = by_telegram(NOW)
    for minute in range(3):
        refused(lambda: verify(db, first, "000000", now=NOW + timedelta(minutes=minute)))
    by_whatsapp = ask(db, now=NOW + timedelta(minutes=3))
    second, code = by_telegram(NOW + timedelta(minutes=4))
    refused(lambda: verify(db, second, "000000", now=NOW + timedelta(minutes=4)))
    fifth = refused(lambda: verify(db, second, "000000", now=NOW + timedelta(minutes=5)))
    assert fifth.code == "too_many_attempts" and fifth.http_status == 429

    locked = NOW + timedelta(minutes=12)
    # Bloqué sur tous les canaux : même le bon code, ni code par WhatsApp,
    # ni nouvelle demande.
    assert refused(lambda: verify(db, second, code, now=locked)).code == "too_many_attempts"
    assert refused(lambda: write(db, by_whatsapp, now=locked)).code == "too_many_attempts"
    assert refused(lambda: ask(db, now=locked)).code == "rate_limited"
    assert db.query(models.LoginFailure).count() == 5

    # 15 minutes après le 5e code faux : de nouveau possible.
    third, code = by_telegram(NOW + timedelta(minutes=20, seconds=1))
    assert verify(db, third, code, now=NOW + timedelta(minutes=21)).existing_account is True


def test_wrong_codes_spread_over_more_than_10_minutes_do_not_lock(db):
    created = ask(db)
    write(db, created)
    for minute in (0, 3, 6, 9):
        refused(lambda: verify(db, created, "000000", now=NOW + timedelta(minutes=minute)))
    later = ask(db, now=NOW + timedelta(minutes=11))
    code = write(db, later, now=NOW + timedelta(minutes=11)).code
    refused(lambda: verify(db, later, "000000", now=NOW + timedelta(minutes=11)))
    assert verify(db, later, code, now=NOW + timedelta(minutes=12)).account_id


def test_old_wrong_codes_are_purged_after_an_hour(db):
    created = ask(db)
    write(db, created)
    refused(lambda: verify(db, created, "000000"))
    later = ask(db, now=NOW + timedelta(minutes=30))
    write(db, later, now=NOW + timedelta(minutes=30))
    refused(lambda: verify(db, later, "000000", now=NOW + timedelta(minutes=30)))
    assert app_auth.purge_login_failures(db, now=NOW + timedelta(hours=1, seconds=1)) == 1
    assert db.query(models.LoginFailure).count() == 1


# --- Route du service WhatsApp : le backend envoie le code ---------------------------


@pytest.fixture
def backend(backend_db_url, monkeypatch):
    importlib.import_module("backend.app.main")
    configure(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    reloaded = importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    main.database = database
    meta = fake_meta(monkeypatch)
    with TestClient(main.app) as client:
        yield client, database, reloaded, meta


def app_login(client, start_token, *, bsuid=BSUID, phone="+243810000009", key=None, language="en"):
    headers = {
        "X-API-Key": WHATSAPP_KEY,
        "X-Actor-Channel": "whatsapp",
        "X-Actor-Id": bsuid,
        "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}",
    }
    body = {"start_token": start_token, "language": language}
    if phone:
        body["phone"] = phone
    return client.post("/api/whatsapp/app-login", json=body, headers=headers)


def test_the_backend_sends_the_code_to_the_whatsapp_that_wrote_and_never_returns_it(backend):
    client, database, reloaded, meta = backend
    with database.SessionLocal() as db:
        created = ask(db, now=datetime.utcnow())

    key = "wamid.app-login-0001"
    response = app_login(client, created.start_token, key=key)

    assert response.status_code == 200, response.text
    assert response.json()["sent"] is True and "code" not in response.json()
    (message,) = meta.sent
    assert message.recipient == BSUID and message.to is None and message.kind == "text"
    code = re.search(r"\*(\d{6})\*", message.text).group(1)
    assert "Never give this code to anyone" in message.text
    with database.SessionLocal() as db:
        stored = db.query(reloaded.IdempotencyKey).filter_by(key=key).one()
        assert code not in repr({column: getattr(stored, column) for column in stored.__table__.columns.keys()})
        events = [event.result for event in db.query(reloaded.AuthEvent).filter_by(type="code_issued")]
        assert events == ["accepted", "wa_sent"]
        assert app_auth.verify_code(
            db, public_id=created.public_id, code=code, device_key_thumbprint=DEVICE
        ).existing_account is False

    # Message rejoué par Meta : même réponse gardée, rien ne repart.
    replay = app_login(client, created.start_token, key=key)
    assert replay.status_code == 200 and "code" not in replay.json()
    assert len(meta.sent) == 1


def test_a_refusal_is_returned_to_the_service_and_nothing_leaves(backend):
    client, database, _reloaded, meta = backend
    with database.SessionLocal() as db:
        created = ask(db, now=datetime.utcnow())

    hidden = app_login(client, created.start_token, phone=None)
    other = app_login(client, created.start_token, phone="+243810000077")

    assert hidden.status_code == 400 and hidden.json()["detail"] == {"code": "phone_hidden"}
    assert other.status_code == 400 and other.json()["detail"] == {"code": "phone_mismatch"}
    assert meta.sent == []


def test_a_meta_failure_is_said_to_the_service(backend):
    client, database, _reloaded, meta = backend
    with database.SessionLocal() as db:
        created = ask(db, now=datetime.utcnow())
    meta.fail_next("error")

    response = app_login(client, created.start_token)

    assert response.status_code == 200 and response.json()["sent"] is False


def test_wrong_codes_on_a_request_that_never_got_a_code_do_not_lock_the_number(db):
    """N'importe qui peut taper le numéro d'un autre dans l'app ; sans le
    WhatsApp de ce numéro, aucun code n'est remis, et ses essais ne bloquent
    pas le vrai titulaire."""
    attacker = ask(db, device="d" * 64)
    for _ in range(app_auth.MAX_CODE_ATTEMPTS):
        refused(lambda: verify(db, attacker, "000000", device="d" * 64))
    assert db.query(models.LoginFailure).count() == 0
    mine = ask(db, now=NOW + timedelta(minutes=1))
    code = write(db, mine, now=NOW + timedelta(minutes=1)).code
    assert verify(db, mine, code, now=NOW + timedelta(minutes=2)).account_id


def test_the_issued_code_never_shows_in_a_repr(db):
    created = ask(db)
    issued = write(db, created)
    assert issued.code not in repr(issued) and created.start_token not in repr(created)


def test_an_attempt_on_a_number_of_another_account_is_kept_in_the_audit_log(backend):
    client, database, reloaded, meta = backend
    with database.SessionLocal() as db:
        whatsapp_client(db)
        created = ask(db, now=datetime.utcnow())

    response = app_login(client, created.start_token, bsuid=OTHER_BSUID)

    assert response.status_code == 409 and meta.sent == []
    with database.SessionLocal() as db:
        results = [event.result for event in db.query(reloaded.AuthEvent).filter_by(type="whatsapp_contact")]
    assert results == ["phone_conflict"]


def test_the_login_code_is_the_only_direct_whatsapp_send_and_goes_to_the_person_who_wrote():
    """Tout message à une autre personne passe par la table `notifications`.
    Seule exception : le code de connexion, en réponse à l'identité WhatsApp
    qui vient d'écrire (`actor.external_id`), depuis la route du service."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app"
    callers = [
        path.name
        for path in root.glob("*.py")
        if "send_login_code(" in path.read_text(encoding="utf-8") and path.name != "notify_whatsapp.py"
    ]
    assert callers == ["main.py"]
    source = (root / "main.py").read_text(encoding="utf-8")
    assert source.count("send_login_code(") == 1
    assert "notify_whatsapp.send_login_code(actor.external_id," in source
