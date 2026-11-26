# ruff: noqa: F811  (fixtures pytest importées de test_whatsapp_postgres)
"""Paiement WhatsApp (étape 6) sur un vrai Postgres : appuis simultanés sur
« Payer ».

Même garde-fou que test_whatsapp_postgres.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.tests.test_mobile_money import FakeGateway
from backend.tests.test_whatsapp_postgres import (  # noqa: F401
    TELEGRAM_KEY,
    URL,
    WHATSAPP_KEY,
    _parallel,
    alembic,
    backend,
    engine,
)

BSUID = "CD.626262626262"
PROVIDER = 7

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


def _whatsapp(key=None):
    return {
        "X-API-Key": WHATSAPP_KEY,
        "X-Actor-Channel": "whatsapp",
        "X-Actor-Id": BSUID,
        "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}",
    }


def _telegram(telegram_id=PROVIDER):
    return {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def _accepted_quote(backend):
    """Prestataire vérifié, client WhatsApp, mission, devis accepté et 100 USD
    au wallet du client."""
    from backend.app import ledger, profils

    with TestClient(backend.app) as api:
        provider = {"full_name": "Prestataire", "phone_number": "+243800000000", "services": ["service_nettoyage"], "communes": ["Gombe"]}
        account_id = api.put("/api/me/provider-profile", json=provider, headers=_telegram()).json()["account_id"]
        with backend.database.SessionLocal() as db:
            profils.verify_provider(db, account_id)
            db.commit()
        assert api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=_telegram()).status_code == 200
        client = {"display_name": "Mado", "language": "fr", "phone": "+243810000006"}
        assert api.post("/api/whatsapp/client", json=client, headers=_whatsapp()).status_code == 200
        mission = {
            "creation_key": "demande-paiement",
            "service": "service_nettoyage",
            "commune": "Gombe",
            "currency": "USD",
            "description": "Nettoyer le salon",
            "destination": {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"},
        }
        mission_id = api.post("/api/bot/missions", json=mission, headers=_whatsapp()).json()["mission"]["mission_id"]
        quote = {"mission_id": mission_id, "amount": 40, "currency": "USD", "delay_hours": 4, "message": ""}
        quote_id = api.post("/api/bot/quotes", json=quote, headers=_telegram()).json()["quote"]["id"]
        assert api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_whatsapp()).status_code == 200
        client_account = api.get("/api/me/profile", headers=_whatsapp()).json()["account_id"]
    with backend.database.SessionLocal() as db:
        ledger.record_opening_balance(db, client_account, "USD", 100)
        db.commit()
    return mission_id, quote_id


def _post(backend, path, body, key=None):
    with TestClient(backend.app) as api:
        response = api.post(path, json=body, headers=_whatsapp(key))
        return response.status_code, response.json()


def test_taps_on_pay_at_the_same_instant_debit_the_wallet_once(backend, engine):
    mission_id, quote_id = _accepted_quote(backend)
    body = {"method": "wallet", "quote_id": quote_id}
    results = _parallel(6, lambda _index: _post(backend, f"/api/bot/missions/{mission_id}/fund", body))

    assert {status for status, _body in results} == {200}, results
    assert len({answer["money"]["funding"]["reference"] for _status, answer in results}) == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM money_operations WHERE kind = 'fund_wallet'")).scalar_one() == 1
        escrow = connection.execute(
            text("SELECT SUM(amount) FROM ledger_entries WHERE account_type = 'escrow' AND account_id = :id"), {"id": mission_id}
        ).scalar_one()
        assert float(escrow) == 40


def test_the_same_pay_message_received_in_parallel_asks_the_phone_once(backend, engine, monkeypatch):
    from backend.app import mobile_money

    gateway = FakeGateway()
    gateway.collection = "pending"
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: gateway)
    mission_id, quote_id = _accepted_quote(backend)
    key = f"wamid.{uuid.uuid4().hex}"
    body = {"quote_id": quote_id, "phone": "+243810000006", "operator": "mpesa"}
    results = _parallel(6, lambda _index: _post(backend, f"/api/bot/missions/{mission_id}/payment-intents", body, key=key))

    assert {status for status, _body in results} == {200}, results
    assert len({answer["intent"]["id"] for _status, answer in results}) == 1
    assert len(gateway.known) == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM payment_intents")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM idempotency_keys WHERE key = :key"), {"key": key}).scalar_one() == 1
