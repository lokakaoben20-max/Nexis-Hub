# ruff: noqa: F811  (fixtures pytest importées de test_whatsapp_missions)
"""Paiement d'une mission depuis WhatsApp (étape 6) : wallet et Mobile Money.

Mêmes règles et mêmes montants que Telegram, au centime ; un message rejoué
ou un double appui ne débite jamais deux fois et ne relance jamais une
demande au téléphone ; seul le client qui paie lit l'état de son paiement ;
jamais un identifiant Telegram dans ce que reçoit le client WhatsApp.
"""

import uuid

import pytest

from backend.tests.test_mobile_money import FakeGateway
from backend.tests.test_whatsapp_channel import BSUID, OTHER_BSUID, as_telegram, as_whatsapp, register
from backend.tests.test_whatsapp_missions import (  # noqa: F401
    PROVIDER,
    api,
    backend,
    create_on_whatsapp,
    request_body,
    verified_provider,
)

PHONE = "+243810000001"
TELEGRAM_CLIENT = 42


@pytest.fixture
def gateway(backend, monkeypatch):
    from backend.app import mobile_money

    fake = FakeGateway()
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: fake)
    return fake


def _key():
    return f"wamid.{uuid.uuid4().hex}"


def _wa(bsuid=BSUID, key=None):
    return {**as_whatsapp(bsuid), "Idempotency-Key": key or _key()}


def _accepted_mission_on_whatsapp(api, backend, amount=40, currency="USD", urgent=True):
    verified_provider(api, backend)
    register(api)
    body = request_body(currency=currency, urgent=urgent)
    mission_id = create_on_whatsapp(api, body).json()["mission"]["mission_id"]
    quote = {"mission_id": mission_id, "amount": amount, "currency": currency, "delay_hours": 4, "message": ""}
    quote_id = api.post("/api/bot/quotes", json=quote, headers=as_telegram(PROVIDER)).json()["quote"]["id"]
    assert api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa()).status_code == 200
    return mission_id, quote_id


def _accepted_mission_on_telegram(api, amount=40, currency="USD", urgent=True):
    assert api.put("/api/me/client-profile", json={"first_name": "Mado"}, headers=as_telegram(TELEGRAM_CLIENT)).status_code == 200
    body = request_body(creation_key="demande-telegram", currency=currency, urgent=urgent)
    mission_id = api.post("/api/bot/missions", json=body, headers=as_telegram(TELEGRAM_CLIENT)).json()["mission"]["mission_id"]
    quote = {"mission_id": mission_id, "amount": amount, "currency": currency, "delay_hours": 4, "message": ""}
    quote_id = api.post("/api/bot/quotes", json=quote, headers=as_telegram(PROVIDER)).json()["quote"]["id"]
    assert api.post(f"/api/bot/quotes/{quote_id}/accept", headers=as_telegram(TELEGRAM_CLIENT)).status_code == 200
    return mission_id, quote_id


def _credit(api, backend, headers, amount, currency="USD"):
    from backend.app import ledger

    account_id = api.get("/api/me/profile", headers=headers).json()["account_id"]
    with backend.database.SessionLocal() as db:
        ledger.record_opening_balance(db, account_id, currency, amount)
        db.commit()


def _wallet(api, headers):
    return api.get("/api/me/wallet", headers=headers).json()["wallet"]["wallet_balance_usd"]


def _operations(backend, kind=None):
    from backend.app.ledger import MoneyOperation

    with backend.database.SessionLocal() as db:
        query = db.query(MoneyOperation)
        if kind is not None:
            query = query.filter(MoneyOperation.kind == kind)
        return query.count()


def _intents(backend):
    from backend.app.models import PaymentIntent

    with backend.database.SessionLocal() as db:
        return [(intent.id, intent.status) for intent in db.query(PaymentIntent).order_by(PaymentIntent.id)]


def _no_telegram_ids(body):
    for forbidden in ("telegram_id", "provider_telegram_id", "requested_by_telegram_id"):
        assert f"'{forbidden}'" not in repr(body)


def _pay_wallet(api, mission_id, quote_id, key=None, bsuid=BSUID):
    return api.post(f"/api/bot/missions/{mission_id}/fund", json={"method": "wallet", "quote_id": quote_id}, headers=_wa(bsuid, key))


def _pay_mobile(api, mission_id, quote_id, key=None, bsuid=BSUID, operator="mpesa"):
    body = {"quote_id": quote_id, "phone": PHONE, "operator": operator}
    return api.post(f"/api/bot/missions/{mission_id}/payment-intents", json=body, headers=_wa(bsuid, key))


# --- Wallet -------------------------------------------------------------------------


def test_a_wallet_payment_gives_the_same_amounts_as_on_telegram_to_the_cent(api, backend):
    whatsapp_mission, whatsapp_quote = _accepted_mission_on_whatsapp(api, backend, amount="37.35")
    telegram_mission, telegram_quote = _accepted_mission_on_telegram(api, amount="37.35")
    _credit(api, backend, as_whatsapp(), 100)
    _credit(api, backend, as_telegram(TELEGRAM_CLIENT), 100)

    on_whatsapp = _pay_wallet(api, whatsapp_mission, whatsapp_quote)
    on_telegram = api.post(
        f"/api/bot/missions/{telegram_mission}/fund",
        json={"method": "wallet", "quote_id": telegram_quote},
        headers=as_telegram(TELEGRAM_CLIENT),
    )
    assert on_whatsapp.status_code == on_telegram.status_code == 200, on_whatsapp.json()
    funded = [response.json()["money"]["funding"] for response in (on_whatsapp, on_telegram)]
    for funding in funded:
        del funding["reference"], funding["quote_ref"]
    assert funded[0] == funded[1]
    assert (funded[0]["total"], funded[0]["commission"], funded[0]["net"]) == ("37.35", "5.60", "31.75")
    assert on_whatsapp.json()["mission"]["payment_status"] == "paid_escrow"
    assert _wallet(api, as_whatsapp()) == _wallet(api, as_telegram(TELEGRAM_CLIENT)) == pytest.approx(62.65)
    _no_telegram_ids(on_whatsapp.json())


def test_a_double_tap_on_pay_debits_once(api, backend):
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    _credit(api, backend, as_whatsapp(), 100)
    key = _key()
    first = _pay_wallet(api, mission_id, quote_id, key=key)
    replay = _pay_wallet(api, mission_id, quote_id, key=key)
    second_tap = _pay_wallet(api, mission_id, quote_id)
    assert first.status_code == replay.status_code == second_tap.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true" and replay.json() == first.json()
    assert second_tap.json()["money"]["funding"]["reference"] == first.json()["money"]["funding"]["reference"]
    assert _operations(backend, "fund_wallet") == 1
    assert _wallet(api, as_whatsapp()) == pytest.approx(60)
    from backend.app.models import Notification

    with backend.database.SessionLocal() as db:
        assert db.query(Notification).filter(Notification.event_key == f"mission_funded:{mission_id}").count() == 1


def test_not_enough_in_the_wallet_moves_nothing(api, backend):
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    _credit(api, backend, as_whatsapp(), 10)
    refused = _pay_wallet(api, mission_id, quote_id)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "insufficient_balance")
    assert refused.json()["detail"]["mission"]["payment_status"] in (None, "unpaid")
    _no_telegram_ids(refused.json())
    assert _operations(backend, "fund_wallet") == 0
    assert _wallet(api, as_whatsapp()) == pytest.approx(10)
    # Rien n'a été retenu pour ce message : une fois le wallet garni, le même
    # message (rejoué par Meta) paie.
    _credit(api, backend, as_whatsapp(), 50)
    assert _pay_wallet(api, mission_id, quote_id).status_code == 200


def test_only_the_client_pays_and_a_payment_needs_its_message_key(api, backend):
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    _credit(api, backend, as_whatsapp(OTHER_BSUID), 100)
    other = _pay_wallet(api, mission_id, quote_id, bsuid=OTHER_BSUID)
    assert (other.status_code, other.json()["detail"]["code"]) == (403, "not_mission_client")
    assert "mission" not in other.json()["detail"]
    no_key = api.post(f"/api/bot/missions/{mission_id}/fund", json={"method": "wallet", "quote_id": quote_id}, headers=as_whatsapp())
    assert (no_key.status_code, no_key.json()["detail"]["code"]) == (400, "idempotency_key_required")
    body = {"quote_id": quote_id, "phone": PHONE, "operator": "mpesa"}
    no_key = api.post(f"/api/bot/missions/{mission_id}/payment-intents", json=body, headers=as_whatsapp())
    assert (no_key.status_code, no_key.json()["detail"]["code"]) == (400, "idempotency_key_required")
    assert _operations(backend) == 1  # le solde de départ de l'autre client, rien d'autre


# --- Mobile Money -------------------------------------------------------------------


def test_a_mobile_money_payment_confirmed_by_the_aggregator_funds_the_mission(api, backend, gateway):
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend, amount=40)
    response = _pay_mobile(api, mission_id, quote_id)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert body["intent"]["status"] == "succeeded" and body["intent"]["amount"] == "40.00"
    assert body["money"]["funding"]["total"] == "40.00" and body["mission"]["payment_status"] == "paid_escrow"
    _no_telegram_ids(body)
    shown = api.get(f"/api/bot/payment-intents/{body['intent']['id']}", headers=as_whatsapp())
    assert shown.status_code == 200 and shown.json()["intent"]["status"] == "succeeded"
    _no_telegram_ids(shown.json())


def test_a_replayed_message_never_sends_a_second_request_to_the_phone(api, backend, gateway):
    """Meta rejoue un message pendant des jours : même après l'échec de la
    première demande, le message rejoué rend cette demande, il n'en ouvre pas
    une nouvelle."""
    gateway.collection = "failed"
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    key = _key()
    first = _pay_mobile(api, mission_id, quote_id, key=key)
    assert first.json()["intent"]["status"] == "failed"
    gateway.collection = "succeeded"
    replay = _pay_mobile(api, mission_id, quote_id, key=key)
    assert replay.status_code == 200 and replay.headers.get("Idempotent-Replayed") == "true"
    assert replay.json()["intent"]["id"] == first.json()["intent"]["id"]
    assert replay.json()["intent"]["status"] == "failed"
    assert len(gateway.known) == 1 and len(_intents(backend)) == 1
    # Un nouvel appui (nouveau message) réessaie : c'est voulu.
    retry = _pay_mobile(api, mission_id, quote_id)
    assert retry.json()["intent"]["status"] == "succeeded" and len(_intents(backend)) == 2


def test_a_double_tap_while_waiting_returns_the_same_request(api, backend, gateway):
    gateway.collection = "pending"
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    first = _pay_mobile(api, mission_id, quote_id)
    second = _pay_mobile(api, mission_id, quote_id, operator="airtel")
    assert first.json()["intent"]["id"] == second.json()["intent"]["id"]
    assert first.json()["intent"]["status"] == second.json()["intent"]["status"] == "pending"
    assert len(gateway.known) == 1
    # Confirmé ensuite (webhook ou vérification de secours) : le client le lit.
    from backend.app import mobile_money

    gateway.collection = "succeeded"
    with backend.database.SessionLocal() as db:
        mobile_money.refresh_intent(db, first.json()["intent"]["id"])
    shown = api.get(f"/api/bot/payment-intents/{first.json()['intent']['id']}", headers=as_whatsapp()).json()
    assert shown["intent"]["status"] == "succeeded" and shown["mission"]["payment_status"] == "paid_escrow"


def test_a_different_amount_never_funds_the_mission(api, backend, gateway):
    gateway.amount = "39.00"
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    body = _pay_mobile(api, mission_id, quote_id).json()
    assert body["intent"]["status"] == "mismatch"
    assert body["mission"]["payment_status"] in (None, "unpaid") and body["money"]["funding"] is None
    assert _operations(backend, "fund_mobile_money") == 0


def test_an_unreachable_aggregator_moves_nothing_and_keeps_one_open_request(api, backend, gateway):
    gateway.down = True
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    key = _key()
    first = _pay_mobile(api, mission_id, quote_id, key=key)
    assert first.status_code == 200 and first.json()["intent"]["status"] == "created"
    assert _pay_mobile(api, mission_id, quote_id, key=key).json()["intent"]["id"] == first.json()["intent"]["id"]
    assert _pay_mobile(api, mission_id, quote_id).json()["intent"]["id"] == first.json()["intent"]["id"]
    assert len(_intents(backend)) == 1 and _operations(backend) == 0


def test_payments_paused_by_an_admin_are_refused_and_nothing_is_kept(api, backend, gateway):
    from backend.app import interrupteurs

    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    with backend.database.SessionLocal() as db:
        interrupteurs.switch(db, interrupteurs.COLLECTIONS, open=False, reason="test", source="cli")
        db.commit()
    key = _key()
    refused = _pay_mobile(api, mission_id, quote_id, key=key)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (503, "payments_paused")
    _no_telegram_ids(refused.json())
    with backend.database.SessionLocal() as db:
        interrupteurs.switch(db, interrupteurs.COLLECTIONS, open=True, reason="test", source="cli")
        db.commit()
    assert _pay_mobile(api, mission_id, quote_id, key=key).json()["intent"]["status"] == "succeeded"


def test_only_the_paying_client_reads_the_payment(api, backend, gateway):
    gateway.collection = "pending"
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend)
    intent_id = _pay_mobile(api, mission_id, quote_id).json()["intent"]["id"]
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    for headers in (as_whatsapp(OTHER_BSUID), as_whatsapp("CD.777000111"), as_telegram(PROVIDER)):
        hidden = api.get(f"/api/bot/payment-intents/{intent_id}", headers=headers)
        assert (hidden.status_code, hidden.json()["detail"]["code"]) == (404, "intent_not_found")
    assert api.get("/api/bot/payment-intents/999", headers=as_whatsapp()).status_code == 404
