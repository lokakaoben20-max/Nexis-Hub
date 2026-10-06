"""Rapprochement interne quotidien (backend/app/reconciliation.py) et
vérification de secours des intentions restées « created ».

Mêmes briques que test_mobile_money.py : un agrégateur de test dont on règle
chaque réponse, une base SQLite jetable par test.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import crud, ledger, mobile_money, reconciliation
from backend.app.payment_gateway import FAILED, PENDING, SUCCEEDED, GatewayResult

LedgerEntry = ledger.LedgerEntry
PaymentIntent = mobile_money.PaymentIntent
Payout = mobile_money.Payout
CLIENT_ID, PROVIDER_ID, ADMIN_ID = 42, 7, 1
PHONE = "+243810000000"


class FakeGateway:
    name = "fake"

    def __init__(self):
        self.collection = "succeeded"
        self.amount = None
        self.payout = "succeeded"
        self.crash_on_request = False

    def request_collection(self, intent):
        if self.crash_on_request:
            raise RuntimeError("backend arrêté pendant l'appel")
        return self.collection_status(intent)

    def collection_status(self, intent):
        status = {"succeeded": SUCCEEDED, "pending": PENDING, "failed": FAILED}[self.collection]
        amount = Decimal(self.amount) if self.amount is not None else intent.amount
        fee = (Decimal(amount) * Decimal("0.025")).quantize(Decimal("0.01"))  # sur l'argent encaissé
        return GatewayResult(status, f"FAKE-{intent.id}", amount, intent.currency, fee)

    def request_payout(self, payout):
        return self.payout_status(payout)

    def payout_status(self, payout):
        status = {"succeeded": SUCCEEDED, "pending": PENDING, "failed": FAILED}[self.payout]
        return GatewayResult(status, f"FAKE-OUT-{payout.id}")


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: fake)
    monkeypatch.setenv("COLLECTION_FEE_RATE", "0.025")
    return fake


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'reco.db'}", future=True)
    LedgerEntry.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    session.add(ledger.BotUser(telegram_id=CLIENT_ID, first_name="Client"))
    session.add(crud.BotProvider(telegram_id=PROVIDER_ID, full_name="Prestataire"))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def request(amount=100.0, quote_ref=5):
    return {
        "client_telegram_id": CLIENT_ID, "provider_telegram_id": PROVIDER_ID, "quote_ref": quote_ref,
        "amount": amount, "currency": "USD", "urgent": False,
        "service": "service_plomberie", "commune": "Gombe", "description": "",
    }


def pay(db, mission_id=1, **kwargs):
    return mobile_money.create_intent(db, mission_id, phone=PHONE, operator="mpesa", funding_request=request(**kwargs))


def complete(db, mission_id):
    ledger.start_mission(db, mission_id, PROVIDER_ID)
    ledger.finish_mission(db, mission_id, PROVIDER_ID)
    ledger.confirm_completion(db, mission_id, CLIENT_ID)


def withdraw(db, amount=20.0):
    return mobile_money.request_payout(db, telegram_id=PROVIDER_ID, amount=amount, currency="USD", phone=PHONE, operator="airtel")


def codes(report):
    return sorted(anomaly["code"] for anomaly in report.anomalies)


def busy_books(db, gateway):
    """Un peu de tout : mission réglée, mission en escrow, paiement en trop,
    retraits versé, refusé, échoué et en attente de l'admin."""
    pay(db, 1)
    complete(db, 1)  # le prestataire gagne 90
    pay(db, 2, quote_ref=6)  # reste en escrow

    gateway.collection = "pending"
    late = pay(db, 3, quote_ref=7)
    late.expires_at -= timedelta(hours=1)
    db.commit()
    mobile_money.refresh_intent(db, late.id)
    gateway.collection = "succeeded"
    pay(db, 3, quote_ref=7)
    mobile_money.refresh_intent(db, late.id)  # payée en trop -> wallet du client

    mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)
    mobile_money.reject_payout(db, withdraw(db).id, ADMIN_ID)
    gateway.payout = "failed"
    mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)
    withdraw(db)  # attend l'admin


def test_consistent_books_give_a_clean_report(db, gateway):
    busy_books(db, gateway)

    report = reconciliation.reconcile(db)

    assert report.anomalies == []
    assert report.counts == {"operations": db.query(ledger.MoneyOperation).count(), "intents": 4, "payouts": 4}
    assert reconciliation.format_admin_report(report).startswith("✅ Rapprochement du ")


def test_an_unbalanced_operation_is_reported(db, gateway):
    pay(db)
    funding = ledger.mission_operation(db, 1, ledger.FUNDING)
    db.add(LedgerEntry(operation_id=funding.id, account_type=ledger.PLATFORM, account_id=None, currency="USD", amount=Decimal("1.00")))
    db.commit()

    assert "unbalanced_operation" in codes(reconciliation.reconcile(db))


def test_escrow_that_does_not_match_the_payment_is_reported(db, gateway):
    pay(db)
    # Mouvement d'escrow écrit hors du registre (équilibré, donc seul le
    # contrôle d'escrow peut le voir).
    operation = ledger.MoneyOperation(kind="manual", details={})
    db.add(operation)
    db.flush()
    db.add(LedgerEntry(operation_id=operation.id, account_type=ledger.ESCROW, account_id=1, currency="USD", amount=Decimal("-10.00")))
    db.add(LedgerEntry(operation_id=operation.id, account_type=ledger.PLATFORM, account_id=None, currency="USD", amount=Decimal("10.00")))
    db.commit()

    assert codes(reconciliation.reconcile(db)) == ["escrow_mismatch"]


def test_a_mission_status_that_disagrees_with_the_ledger_is_reported(db, gateway):
    pay(db)
    complete(db, 1)
    db.get(ledger.BotMission, 1).payment_status = "paid_escrow"
    db.commit()

    assert codes(reconciliation.reconcile(db)) == ["mission_status_mismatch"]


def test_a_payout_whose_status_disagrees_with_the_held_money_is_reported(db, gateway):
    pay(db)
    complete(db, 1)
    payout = withdraw(db)
    payout.status = "succeeded"  # jamais versé au registre
    db.commit()

    assert codes(reconciliation.reconcile(db)) == ["payout_hold_mismatch", "payout_operations_mismatch"]


def test_money_received_with_a_different_amount_stays_reported_until_the_admin_decides(db, gateway):
    gateway.amount = "99.00"
    pay(db)

    report = reconciliation.reconcile(db)
    assert codes(report) == ["intent_amount_mismatch"]
    assert "décision de l'admin requise" in reconciliation.format_admin_report(report)


def test_a_fee_different_from_the_expected_rate_is_reported(db, gateway, monkeypatch):
    pay(db)
    monkeypatch.setenv("COLLECTION_FEE_RATE", "0.03")

    assert codes(reconciliation.reconcile(db)) == ["fee_deviation"]


def test_a_mobile_money_payment_without_a_confirmed_intent_is_reported(db, gateway):
    base = request()
    ledger.fund_mission(db, 1, method="mobile_money", reference="FAKE-999", **base)
    ledger.fund_mission(db, 2, method="mobile_money", **{**base, "quote_ref": 6})  # ancien paiement simulé « SIM-0006 »

    report = reconciliation.reconcile(db)
    assert codes(report) == ["funding_without_intent"]
    assert "FAKE-999" in report.anomalies[0]["detail"]


def test_long_running_payouts_are_reported(db, gateway):
    pay(db)
    complete(db, 1)
    gateway.payout = "pending"
    payout = withdraw(db)
    mobile_money.approve_payout(db, payout.id, ADMIN_ID)
    now = ledger._utcnow()

    assert reconciliation.reconcile(db, now).anomalies == []
    assert codes(reconciliation.reconcile(db, now + timedelta(hours=25))) == ["payout_stuck"]


# --- Intention restée « created » (backend arrêté pendant l'appel) -----------------


def test_an_intent_left_created_is_refreshed_then_funds_the_mission(db, gateway):
    gateway.crash_on_request = True
    with pytest.raises(RuntimeError):
        pay(db)
    intent = db.query(PaymentIntent).one()
    assert intent.status == "created"
    now = ledger._utcnow()

    assert mobile_money.intents_to_refresh(db, now) == [], "demande peut-être encore en cours"
    assert codes(reconciliation.reconcile(db, now + timedelta(minutes=11))) == ["intent_stuck"]

    later = now + timedelta(minutes=3)
    assert mobile_money.intents_to_refresh(db, later) == [intent.id]
    for intent_id in mobile_money.intents_to_refresh(db, later):
        mobile_money.refresh_intent(db, intent_id)

    assert db.get(PaymentIntent, intent.id).status == "succeeded"
    assert ledger.balance(db, ledger.ESCROW, 1, "USD") == Decimal("100.00")
    assert reconciliation.reconcile(db, now + timedelta(minutes=11)).anomalies == []


def test_late_and_pending_intents_are_refreshed_but_not_old_ones(db, gateway):
    gateway.collection = "pending"
    pending = pay(db, 1)
    expired = pay(db, 2, quote_ref=6)
    expired.status, expired.expires_at = "expired", ledger._utcnow() - timedelta(hours=25)
    db.commit()

    assert mobile_money.intents_to_refresh(db, ledger._utcnow()) == [pending.id]


def test_admin_report_lists_anomalies_and_never_corrects():
    report = reconciliation.Report(generated_at=ledger._utcnow(), counts={"operations": 3, "intents": 1, "payouts": 0})
    for index in range(25):
        report.add("escrow_mismatch", f"écart {index}")

    text = reconciliation.format_admin_report(report)
    assert "25 écart(s)" in text and "Aucune correction automatique" in text
    assert "• écart 19" in text and "écart 20" not in text
    assert "… et 5 autre(s)." in text
