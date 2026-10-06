"""Paiement reçu avec un montant différent de la demande : décision de l'admin
(`mobile_money.resolve_mismatch`). Mêmes briques que test_reconciliation.py."""

from decimal import Decimal

import pytest

from backend.app import ledger, mobile_money, reconciliation
from backend.app.ledger import MoneyError
from backend.app.payment_gateway import GatewayUnavailable
from backend.tests.test_reconciliation import (  # noqa: F401 (fixtures)
    ADMIN_ID,
    CLIENT_ID,
    PaymentIntent,
    codes,
    db,
    gateway,
    pay,
)

USD = "USD"


def client_account(db):
    return ledger.account_id_for(db, ledger.TELEGRAM, CLIENT_ID)


def wallet(db, currency=USD):
    return ledger.balance(db, ledger.WALLET, client_account(db), currency)


def mismatched(db, gateway, received="99.00"):
    gateway.amount = received
    intent = pay(db)
    assert intent.status == "mismatch"
    return intent


def test_a_different_amount_is_kept_aside_with_what_was_received(db, gateway):
    intent = mismatched(db, gateway)

    assert (intent.received_amount, intent.received_currency) == (Decimal("99.00"), USD)
    assert db.get(ledger.BotMission, 1).payment_status in (None, "unpaid")
    assert db.query(ledger.MoneyOperation).count() == 0  # hors registre
    assert [i.id for i in mobile_money.list_mismatches(db)] == [intent.id]


def test_credit_wallet_puts_the_received_amount_on_the_client_wallet_once(db, gateway):
    intent = mismatched(db, gateway)

    resolved, changed = mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")

    assert changed and resolved.status == "mismatch_credited"
    assert resolved.resolved_by_telegram_id == ADMIN_ID and resolved.resolved_at is not None
    assert wallet(db) == Decimal("99.00")
    assert db.get(ledger.BotMission, 1).payment_status in (None, "unpaid")
    # Comme un trop-perçu : retirable seulement après vérification admin.
    assert ledger.withdrawable_without_review(db, client_account(db), USD) == Decimal("0.00")
    assert reconciliation.reconcile(db).anomalies == []
    assert mobile_money.list_mismatches(db) == []

    replay, changed = mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")
    assert not changed and replay.status == "mismatch_credited"
    assert wallet(db) == Decimal("99.00")
    with pytest.raises(MoneyError) as other:
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "pay_mission")
    assert other.value.code == "already_resolved"


def test_pay_mission_pays_the_quote_from_the_received_money_and_keeps_the_surplus(db, gateway):
    intent = mismatched(db, gateway, received="105.00")

    resolved, changed = mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "pay_mission")

    assert changed and resolved.status == "mismatch_paid"
    mission = db.get(ledger.BotMission, 1)
    assert (mission.payment_status, mission.status) == ("paid_escrow", "confirmed")
    assert ledger.balance(db, ledger.ESCROW, 1, USD) == Decimal("100.00")
    assert wallet(db) == Decimal("5.00")
    assert ledger.mission_operation(db, 1, ledger.FUNDING).reference == intent.gateway_reference
    assert reconciliation.reconcile(db).anomalies == []


def test_pay_mission_is_refused_when_the_received_money_is_not_enough(db, gateway):
    intent = mismatched(db, gateway)

    with pytest.raises(MoneyError) as refused:
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "pay_mission")

    assert refused.value.code == "received_amount_too_low"
    assert db.get(PaymentIntent, intent.id).status == "mismatch"
    assert db.query(ledger.MoneyOperation).count() == 0
    # Verrou libéré : l'autre décision reste possible.
    assert mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")[0].status == "mismatch_credited"


def test_pay_mission_on_a_mission_paid_meanwhile_moves_nothing(db, gateway):
    intent = mismatched(db, gateway, received="105.00")
    gateway.amount = None
    pay(db)  # le client a repayé le bon montant
    before = db.query(ledger.MoneyOperation).count()

    with pytest.raises(MoneyError) as refused:
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "pay_mission")

    assert refused.value.code == "already_paid"
    assert db.query(ledger.MoneyOperation).count() == before  # crédit annulé avec le paiement
    assert db.get(PaymentIntent, intent.id).status == "mismatch"
    gateway.amount = "105.00"
    mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")
    assert wallet(db) == Decimal("105.00")
    assert reconciliation.reconcile(db).anomalies == []


def test_the_amount_is_read_again_from_the_aggregator_when_deciding(db, gateway):
    intent = mismatched(db, gateway, received="99.00")
    gateway.amount = "98.00"  # ce que l'agrégateur dit aujourd'hui fait foi

    resolved, _ = mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")

    assert resolved.received_amount == Decimal("98.00")
    assert wallet(db) == Decimal("98.00")


@pytest.mark.parametrize("answer, code", [("down", "gateway_unavailable"), ("failed", "gateway_not_confirmed")])
def test_nothing_moves_when_the_aggregator_does_not_confirm(db, gateway, monkeypatch, answer, code):
    intent = mismatched(db, gateway)
    if answer == "down":
        def unavailable(_intent):
            raise GatewayUnavailable("timeout")
        monkeypatch.setattr(gateway, "collection_status", unavailable)
    else:
        gateway.collection = "failed"

    with pytest.raises(MoneyError) as refused:
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")

    assert refused.value.code == code
    assert db.get(PaymentIntent, intent.id).status == "mismatch"
    assert db.query(ledger.MoneyOperation).count() == 0


def test_unknown_decision_or_intent_is_refused(db, gateway):
    intent = mismatched(db, gateway)
    with pytest.raises(MoneyError) as refused:
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "split")
    assert refused.value.code == "invalid_decision"
    with pytest.raises(MoneyError) as missing:
        mobile_money.resolve_mismatch(db, 999, ADMIN_ID, "credit_wallet")
    assert missing.value.code == "intent_not_found"
    gateway.amount = None
    with pytest.raises(MoneyError) as not_mismatch:
        mobile_money.resolve_mismatch(db, pay(db, 2, quote_ref=6).id, ADMIN_ID, "credit_wallet")
    assert not_mismatch.value.code == "invalid_state"


def test_a_resolved_intent_without_its_ledger_credit_is_reported(db, gateway):
    intent = mismatched(db, gateway)
    intent.status, intent.received_amount = "mismatch_credited", Decimal("99.00")
    db.commit()

    assert "intent_not_in_ledger" in codes(reconciliation.reconcile(db))


def test_the_reference_read_when_deciding_is_kept_on_the_intent(db, gateway, monkeypatch):
    intent = mismatched(db, gateway)
    intent.gateway_reference = None  # première réponse sans référence
    db.commit()

    resolved, _ = mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")

    assert resolved.gateway_reference == f"FAKE-{intent.id}"
    assert reconciliation.reconcile(db).anomalies == []


def test_no_reference_at_all_moves_nothing(db, gateway, monkeypatch):
    intent = mismatched(db, gateway)
    intent.gateway_reference = None
    db.commit()
    real = gateway.collection_status
    monkeypatch.setattr(gateway, "collection_status", lambda i: real(i).__class__(**{**real(i).__dict__, "reference": None}))

    with pytest.raises(MoneyError) as refused:
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")

    assert refused.value.code == "missing_reference"
    assert db.query(ledger.MoneyOperation).count() == 0


def test_a_failure_inside_the_mission_payment_cancels_the_credit_too(db, gateway, monkeypatch):
    intent = mismatched(db, gateway, received="105.00")

    def broken_fund_mission(*args, **kwargs):
        raise MoneyError("insufficient_balance")
    monkeypatch.setattr(ledger, "fund_mission", broken_fund_mission)

    with pytest.raises(MoneyError):
        mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "pay_mission")

    assert db.query(ledger.MoneyOperation).count() == 0
    assert wallet(db) == Decimal("0.00")
    assert db.get(PaymentIntent, intent.id).status == "mismatch"


def test_a_credit_without_a_recorded_decision_is_reported(db, gateway):
    intent = mismatched(db, gateway)
    ledger.record_mismatch_credit(
        db, account_id=intent.account_id, currency=USD, amount="99.00", reference=intent.gateway_reference,
        mission_id=1, admin_telegram_id=ADMIN_ID,
    )
    db.commit()  # écrit, mais l'intention est restée « mismatch »

    assert "mismatch_credit_without_decision" in codes(reconciliation.reconcile(db))


def test_a_credit_on_another_account_is_reported(db, gateway):
    intent = mismatched(db, gateway)
    mobile_money.resolve_mismatch(db, intent.id, ADMIN_ID, "credit_wallet")
    entry = db.query(ledger.LedgerEntry).filter(ledger.LedgerEntry.account_type == ledger.WALLET).one()
    entry.account_id = ledger.account_id_for(db, ledger.TELEGRAM, 7, create=True)
    db.commit()

    assert "mismatch_credit_mismatch" in codes(reconciliation.reconcile(db))
