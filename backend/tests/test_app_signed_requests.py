"""Demandes signées, argent sortant et « Ce n'est pas moi » de l'application
mobile (étape 1, PR 4) : tests d'attaque et cas normaux.

Plan : app-mobile/plan-etape1-connexion-api-2026-11-07.md, sections 5.5, 5.7
et 5.8.
"""

import json
from datetime import timedelta

import pytest
from celery.exceptions import Retry

from backend.app import app_sessions, ledger, models, tasks
from test_app_sessions import (  # noqa: F401 - fixtures partagées
    NOW,
    Phone,
    _as,
    code_for,
    backend,
    code_key,
    db,
    device,
    refused,
    sign_in,
)

BODY = json.dumps({"amount": "25.00", "currency": "USD", "idempotency_key": "k-1"}).encode()
PATH = "/api/app/v1/me/payouts"


def epoch(moment):
    return str(int((moment - app_sessions._EPOCH).total_seconds()))


class Request:
    """Une demande de l'app, signée comme le ferait le téléphone."""

    counter = 0

    def __init__(self, phone, tokens, *, method="POST", path=PATH, body=BODY, sent_at=NOW, nonce=None):
        Request.counter += 1
        self.values = dict(
            access_token=tokens.access_token,
            method=method,
            path=path,
            body=body,
            timestamp=epoch(sent_at),
            nonce=nonce or f"nonce-{Request.counter:04d}-abcdefghijklmnop",
        )
        self.values["signature"] = phone.sign(app_sessions.request_message(**self.values))

    def but(self, **changes):
        changed = Request.__new__(Request)
        changed.values = {**self.values, **changes}
        return changed


def signed(db, request, now=NOW):
    return app_sessions.verify_signed_request(db, now=now, **request.values)


def money(db, request, now=NOW):
    return app_sessions.verify_money_request(db, now=now, **request.values)


def verified(db, tokens):
    row = device(db, tokens)
    row.attestation = "verified"
    db.commit()
    return row


def events(db, type_):
    return [event.result for event in db.query(models.AuthEvent).filter(models.AuthEvent.type == type_)]


def existing_account(db, telegram_id=601):
    ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    db.commit()


# --- Demandes signées ---------------------------------------------------------


def test_a_correctly_signed_request_passes_and_its_nonce_is_kept(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    request = Request(phone, tokens)

    principal = signed(db, request)

    assert (principal.account_id, principal.device_id) == (tokens.account_id, tokens.device_id)
    assert [n.nonce for n in db.query(models.RequestNonce)] == [request.values["nonce"]]


def test_a_replayed_request_is_refused(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    request = Request(phone, tokens)
    signed(db, request)

    refused("replayed_request", signed, db, request, now=NOW + timedelta(seconds=5))

    assert events(db, "signed_request") == ["replayed"]


def test_the_same_nonce_on_two_phones_is_two_different_requests(db):
    first, second = Phone(), Phone()
    first_tokens = sign_in(db, first, telegram_id=601)
    public_id, code = code_for(db, second, telegram_id=602, number="+243810000002")
    second_tokens = app_sessions.sign_in(
        db, challenge_public_id=public_id, code=code, public_key=second.public_key,
        signature=second.sign(app_sessions.login_message(public_id)), platform="ios", app_version="1.0.0", now=NOW,
    )

    signed(db, Request(first, first_tokens, nonce="shared-nonce-0123456789abc"))
    signed(db, Request(second, second_tokens, nonce="shared-nonce-0123456789abc"))

    assert db.query(models.RequestNonce).count() == 2


def test_a_signature_from_another_phone_is_refused_and_burns_no_nonce(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    thief = Phone()
    request = Request(thief, tokens)

    refused("invalid_signature", signed, db, request)

    assert db.query(models.RequestNonce).count() == 0
    assert events(db, "signed_request") == ["bad_signature"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("body", BODY.replace(b"25.00", b"2500.00")),
        ("path", "/api/app/v1/me/payout-number"),
        ("method", "DELETE"),
        ("timestamp", epoch(NOW + timedelta(seconds=1))),
        ("nonce", "another-nonce-0123456789abcdef"),
    ],
)
def test_changing_any_signed_part_breaks_the_signature(db, field, value):
    phone = Phone()
    tokens = sign_in(db, phone)

    refused("invalid_signature", signed, db, Request(phone, tokens).but(**{field: value}))


def test_a_signature_is_bound_to_its_session(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    request = Request(phone, tokens)
    renewed = app_sessions.refresh(
        db, refresh_token=tokens.refresh_token,
        signature=phone.sign(app_sessions.refresh_message(tokens.refresh_token)), now=NOW,
    )

    refused("invalid_signature", signed, db, request.but(access_token=renewed.access_token))


@pytest.mark.parametrize("shift,accepted", [(-300, True), (300, True), (-301, False), (301, False), (-3600, False)])
def test_requests_more_than_5_minutes_off_are_refused(db, shift, accepted):
    phone = Phone()
    tokens = sign_in(db, phone)
    request = Request(phone, tokens, sent_at=NOW + timedelta(seconds=shift))

    if accepted:
        signed(db, request)
    else:
        refused("stale_request", signed, db, request)
        assert db.query(models.RequestNonce).count() == 0


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("nonce", "short", "invalid_nonce"),
        ("nonce", "with spaces in the nonce 0123", "invalid_nonce"),
        ("nonce", None, "invalid_nonce"),
        ("timestamp", "-60", "invalid_timestamp"),
        ("timestamp", "1.5e9", "invalid_timestamp"),
        ("timestamp", None, "invalid_timestamp"),
    ],
)
def test_malformed_nonces_and_timestamps_are_refused(db, field, value, expected):
    phone = Phone()
    tokens = sign_in(db, phone)
    request = Request(phone, tokens, **({"nonce": value} if field == "nonce" and value else {}))

    refused(expected, signed, db, request.but(**{field: value}))


def test_a_signed_request_needs_a_live_session(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    request = Request(phone, tokens)
    app_sessions.revoke_all_devices(db, tokens.account_id, now=NOW)

    refused("unauthorized", signed, db, request)
    refused("unauthorized", signed, db, request.but(access_token="unknown"))


def test_an_expired_session_cannot_sign(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    later = NOW + timedelta(minutes=16)

    refused("unauthorized", signed, db, Request(phone, tokens, sent_at=later), now=later)


def test_old_nonces_are_purged_after_24_hours_only(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    signed(db, Request(phone, tokens, nonce="old-nonce-0123456789abcdef"))
    later = NOW + timedelta(minutes=10)
    signed(db, Request(phone, tokens, nonce="new-nonce-0123456789abcdef", sent_at=later), now=later)

    deleted = app_sessions.purge_request_nonces(db, now=NOW + timedelta(hours=24, seconds=1))

    assert deleted == 1
    assert [n.nonce for n in db.query(models.RequestNonce)] == ["new-nonce-0123456789abcdef"]


# --- Argent sortant -----------------------------------------------------------


def test_no_money_leaves_from_a_phone_not_verified_by_google_or_apple(db):
    phone = Phone()
    tokens = sign_in(db, phone)

    refused("device_not_attested", money, db, Request(phone, tokens))

    assert events(db, "money_request") == ["device_not_attested"]


def test_a_verified_first_phone_of_a_new_account_can_move_money(db):
    phone = Phone()
    tokens = sign_in(db, phone)
    verified(db, tokens)

    assert money(db, Request(phone, tokens)).device_id == tokens.device_id


def test_a_new_phone_on_an_existing_account_waits_72_hours_to_the_second(db):
    existing_account(db)
    phone = Phone()
    tokens = sign_in(db, phone)
    verified(db, tokens)
    unlock = NOW + timedelta(hours=72)
    before = unlock - timedelta(seconds=1)

    # La session d'origine a expiré depuis longtemps : l'app l'a renouvelée.
    renewed = app_sessions.refresh(
        db, refresh_token=tokens.refresh_token,
        signature=phone.sign(app_sessions.refresh_message(tokens.refresh_token)), now=before,
    )
    refused("new_device_locked", money, db, Request(phone, renewed, sent_at=before), now=before)

    assert money(db, Request(phone, renewed, sent_at=unlock), now=unlock).device_id == tokens.device_id


def test_reading_is_allowed_on_an_unverified_phone(db):
    phone = Phone()
    tokens = sign_in(db, phone)

    assert signed(db, Request(phone, tokens, method="DELETE", path="/api/app/v1/me/devices/7", body=b""))
    assert app_sessions.money_allowed(device(db, tokens), NOW) == "device_not_attested"


# --- « Ce n'est pas moi » -----------------------------------------------------


def test_not_me_cuts_the_phone_and_all_its_sessions_at_once(db):
    existing_account(db)
    phone = Phone()
    tokens = sign_in(db, phone)

    row, revoked_now = app_sessions.report_not_me(db, account_id=tokens.account_id, device_id=tokens.device_id, now=NOW)

    assert revoked_now and row.revoked_reason == "not_me"
    refused("unauthorized", app_sessions.authenticate, db, tokens.access_token, now=NOW)
    assert all(s.revoked_reason == "not_me" for s in db.query(models.AppSession))
    assert events(db, "device_revoked") == ["not_me"]


def test_pressing_not_me_twice_changes_nothing_more(db):
    tokens = sign_in(db, Phone())
    app_sessions.report_not_me(db, account_id=tokens.account_id, device_id=tokens.device_id, now=NOW)

    row, revoked_now = app_sessions.report_not_me(
        db, account_id=tokens.account_id, device_id=tokens.device_id, now=NOW + timedelta(minutes=1)
    )

    assert not revoked_now and row.revoked_at == NOW
    assert events(db, "device_revoked") == ["not_me"]


def test_nobody_can_cut_the_phone_of_another_account_with_not_me(db):
    tokens = sign_in(db, Phone())

    refused("device_not_found", app_sessions.report_not_me, db, account_id=tokens.account_id + 1, device_id=tokens.device_id)
    refused("device_not_found", app_sessions.report_not_me, db, account_id=tokens.account_id, device_id=9999)

    assert device(db, tokens).revoked_at is None


def test_only_phones_added_to_an_existing_account_raise_an_alert(db):
    new_account_tokens = sign_in(db, Phone(), telegram_id=601)
    assert new_account_tokens.new_device
    assert not app_sessions.needs_new_device_alert(device(db, new_account_tokens))

    phone = Phone()
    added = sign_in(db, phone, telegram_id=601, now=NOW + timedelta(minutes=1))
    assert added.new_device and app_sessions.needs_new_device_alert(device(db, added))

    app_sessions.revoke_own_device(
        db, app_sessions.authenticate(db, new_account_tokens.access_token, now=NOW), added.device_id, now=NOW
    )
    assert not app_sessions.needs_new_device_alert(device(db, added))


def test_signing_in_again_with_a_known_phone_is_not_a_new_device(db):
    phone = Phone()
    first = sign_in(db, phone)
    app_sessions.sign_out(db, app_sessions.authenticate(db, first.access_token, now=NOW), now=NOW)

    again = sign_in(db, phone, now=NOW + timedelta(minutes=1))

    assert again.device_id == first.device_id and not again.new_device


# --- Alerte « Nouvel appareil » -----------------------------------------------


@pytest.fixture
def telegram(monkeypatch):
    sent = []
    outcome = {"ok": True}

    def fake(telegram_id, text, reply_markup=None):
        sent.append((telegram_id, text, reply_markup))
        return outcome["ok"]

    monkeypatch.setattr(tasks, "send_telegram_message", fake)
    return sent, outcome


def test_the_alert_names_the_phone_and_offers_not_me(db, telegram):
    sent, _ = telegram
    existing_account(db)
    tokens = sign_in(db, Phone())

    assert tasks.send_new_device_alert(db, tokens.device_id)

    [(telegram_id, text, markup)] = sent
    assert telegram_id == 601
    assert "Samsung A54" in text and "07/11/2026" in text and "09:00" in text  # heure de Kinshasa
    assert markup["inline_keyboard"][0][0]["callback_data"] == f"app_not_me_{tokens.device_id}"


def test_no_alert_for_the_first_phone_of_a_brand_new_account(db, telegram):
    sent, _ = telegram
    tokens = sign_in(db, Phone())

    assert tasks.send_new_device_alert(db, tokens.device_id)
    assert sent == []


def test_a_failed_alert_is_retried(db, telegram, monkeypatch):
    _, outcome = telegram
    outcome["ok"] = False
    existing_account(db)
    tokens = sign_in(db, Phone())
    monkeypatch.setattr(tasks, "SessionLocal", lambda: db)
    monkeypatch.setattr(db, "close", lambda: None)

    assert not tasks.send_new_device_alert(db, tokens.device_id)
    with pytest.raises(Retry):
        tasks.alert_new_app_device.run(tokens.device_id)


@pytest.mark.parametrize("lang", ["fr", "en", "ln"])
def test_the_alert_exists_in_every_language(lang):
    from messages import get_message

    text = get_message("app_new_device_alert", lang, device="Samsung A54", date="07/11/2026", time="09:00")

    assert "Samsung A54" in text and "72" in text
    assert get_message("button_app_not_me", lang)


# --- Route du bot « Ce n'est pas moi » ----------------------------------------


@pytest.fixture
def admin_alerts(monkeypatch):
    alerts = []
    monkeypatch.setattr(tasks, "_alert_admin", alerts.append)
    return alerts


def test_not_me_from_telegram_cuts_the_phone_and_alerts_the_admin(backend, admin_alerts):
    client, database = backend
    with database.SessionLocal() as session:
        tokens = sign_in(session, Phone(), telegram_id=601)

    response = client.post(f"/api/bot/app-devices/{tokens.device_id}/not-me", json={}, headers=_as(601))
    again = client.post(f"/api/bot/app-devices/{tokens.device_id}/not-me", json={}, headers=_as(601))

    assert response.status_code == 200 and response.json()["already"] is False
    assert again.status_code == 200 and again.json()["already"] is True
    assert len(admin_alerts) == 1 and str(tokens.device_id) in admin_alerts[0]
    with database.SessionLocal() as session:
        assert session.get(models.Device, tokens.device_id).revoked_reason == "not_me"


@pytest.mark.parametrize("telegram_id", [602, 12345])
def test_not_me_cannot_touch_the_phone_of_someone_else(backend, admin_alerts, telegram_id):
    client, database = backend
    with database.SessionLocal() as session:
        tokens = sign_in(session, Phone(), telegram_id=601)
        # 602 a aussi un compte Nexis ; 12345 n'en a pas.
        code_for(session, Phone(), telegram_id=602, number="+243810000002")

    response = client.post(f"/api/bot/app-devices/{tokens.device_id}/not-me", json={}, headers=_as(telegram_id))

    assert response.status_code == 404 and response.json()["detail"] == {"code": "device_not_found"}
    assert admin_alerts == []
    with database.SessionLocal() as session:
        assert session.get(models.Device, tokens.device_id).revoked_at is None
