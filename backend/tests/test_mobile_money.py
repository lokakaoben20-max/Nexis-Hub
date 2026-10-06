"""Paiements et retraits Mobile Money (backend/app/mobile_money.py), avec un
agrégateur de test dont on règle chaque réponse.

Classes prises dans `ledger` / `crud` : voir test_ledger.py.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend.app import crud, ledger, mobile_money
from backend.app.payment_gateway import FAILED, PENDING, SUCCEEDED, GatewayResult, GatewayUnavailable

LedgerEntry = ledger.LedgerEntry
PaymentIntent = mobile_money.PaymentIntent
Payout = mobile_money.Payout
CLIENT_ID, PROVIDER_ID, ADMIN_ID = 42, 7, 1
PHONE = "+243810000000"


class FakeGateway:
    """Agrégateur de test : `collection` / `payout` disent ce qu'il répondra."""

    name = "fake"

    def __init__(self):
        self.collection = "succeeded"
        self.amount = None
        self.fee = Decimal("2.50")
        self.payout = "succeeded"
        self.down = False
        self.payout_requests = 0

    def _check(self):
        if self.down:
            raise GatewayUnavailable()

    def request_collection(self, intent):
        self._check()
        return self.collection_status(intent)

    def collection_status(self, intent):
        self._check()
        status = {"succeeded": SUCCEEDED, "pending": PENDING, "failed": FAILED}[self.collection]
        amount = self.amount if self.amount is not None else intent.amount
        return GatewayResult(status, f"FAKE-{intent.id}", Decimal(amount), intent.currency, self.fee, "refusé" if status == FAILED else None)

    def request_payout(self, payout):
        self.payout_requests += 1
        self._check()
        return self.payout_status(payout)

    def payout_status(self, payout):
        self._check()
        status = {"succeeded": SUCCEEDED, "pending": PENDING, "failed": FAILED}[self.payout]
        return GatewayResult(status, f"FAKE-OUT-{payout.id}")


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: fake)
    return fake


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'mm.db'}", future=True)
    LedgerEntry.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    session.add(ledger.BotUser(telegram_id=CLIENT_ID, first_name="Client"))
    session.add(crud.BotProvider(telegram_id=PROVIDER_ID, full_name="Prestataire"))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def request(mission_id=1, amount=100.0, quote_ref=5, client=CLIENT_ID, provider=PROVIDER_ID):
    return {
        "client_telegram_id": client, "provider_telegram_id": provider, "quote_ref": quote_ref,
        "amount": amount, "currency": "USD", "urgent": False,
        "service": "service_plomberie", "commune": "Gombe", "description": "",
    }


def pay(db, mission_id=1, **kwargs):
    return mobile_money.create_intent(db, mission_id, phone=PHONE, operator="mpesa", funding_request=request(mission_id, **kwargs))


def wallet(db, telegram_id, currency="USD"):
    return ledger.wallet_balances(db, ledger.TELEGRAM, telegram_id)[currency]


def balance(db, account_type, account_id=None, currency="USD"):
    return ledger.balance(db, account_type, account_id, currency)


def credit(db, telegram_id, amount):
    ledger.record_opening_balance(db, ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True), "USD", amount)
    db.commit()


def assert_books_balanced(db):
    totals = db.query(LedgerEntry.operation_id, func.sum(LedgerEntry.amount)).group_by(LedgerEntry.operation_id).all()
    assert all(money(total) == 0 for _, total in totals), totals


def refused(code, call):
    with pytest.raises(ledger.MoneyError) as error:
        call()
    assert error.value.code == code


# --- Encaissement -------------------------------------------------------------------


def test_a_confirmed_payment_funds_the_mission_and_records_the_fee_on_the_platform(db, gateway):
    intent = pay(db)

    assert intent.status == "succeeded"
    assert db.get(ledger.BotMission, 1).payment_status == "paid_escrow"
    assert balance(db, ledger.ESCROW, 1) == money(100)
    assert balance(db, ledger.FEES) == money("2.50")
    assert balance(db, ledger.PLATFORM) == money("-2.50")  # frais à la charge de Nexis Hub
    assert ledger.mission_money_state(db, 1)["funding"]["reference"] == "FAKE-1"
    assert_books_balanced(db)


def test_nothing_moves_until_the_aggregator_confirms(db, gateway):
    gateway.collection = "pending"
    intent = pay(db)

    assert intent.status == "pending"
    assert balance(db, ledger.ESCROW, 1) == 0
    assert db.get(ledger.BotMission, 1).payment_status is None

    gateway.collection = "succeeded"
    assert mobile_money.refresh_intent(db, intent.id).status == "succeeded"
    assert balance(db, ledger.ESCROW, 1) == money(100)


def test_a_second_click_returns_the_same_open_intent(db, gateway):
    gateway.collection = "pending"
    first, second = pay(db), pay(db)

    assert first.id == second.id
    assert db.query(PaymentIntent).count() == 1


def test_a_refused_payment_moves_nothing_and_can_be_retried(db, gateway):
    gateway.collection = "failed"
    assert pay(db).status == "failed"
    assert balance(db, ledger.ESCROW, 1) == 0

    gateway.collection = "succeeded"
    assert pay(db).status == "succeeded"


def test_a_different_amount_never_funds_the_mission(db, gateway):
    gateway.amount = "99.00"
    intent = pay(db)

    assert intent.status == "mismatch"
    assert balance(db, ledger.ESCROW, 1) == 0
    assert db.query(ledger.MoneyOperation).count() == 0


def test_an_expired_intent_confirmed_late_still_funds_the_unpaid_mission(db, gateway):
    gateway.collection = "pending"
    intent = pay(db)
    intent.expires_at = intent.expires_at - timedelta(hours=1)
    db.commit()
    assert mobile_money.refresh_intent(db, intent.id).status == "expired"

    gateway.collection = "succeeded"
    assert mobile_money.refresh_intent(db, intent.id).status == "succeeded"
    assert balance(db, ledger.ESCROW, 1) == money(100)


def test_money_received_for_an_already_paid_mission_goes_to_the_client_wallet(db, gateway):
    gateway.collection = "pending"
    late = pay(db)
    late.expires_at = late.expires_at - timedelta(hours=1)
    db.commit()
    mobile_money.refresh_intent(db, late.id)  # expirée
    gateway.collection = "succeeded"
    assert pay(db).status == "succeeded"  # nouvelle intention, mission payée

    assert mobile_money.refresh_intent(db, late.id).status == "overpaid"
    assert balance(db, ledger.ESCROW, 1) == money(100)  # jamais payée deux fois
    assert wallet(db, CLIENT_ID) == money(100)  # l'argent en trop n'est pas perdu
    assert_books_balanced(db)


def test_a_replayed_confirmation_does_nothing(db, gateway):
    intent = pay(db)
    mobile_money.refresh_intent(db, intent.id)
    mobile_money.refresh_intent(db, intent.id)

    assert db.query(ledger.MoneyOperation).filter_by(kind="fund_mobile_money").count() == 1
    assert balance(db, ledger.FEES) == money("2.50")


def test_an_unreachable_aggregator_moves_nothing(db, gateway):
    gateway.down = True
    refused("gateway_unavailable", lambda: pay(db))
    assert db.query(ledger.MoneyOperation).count() == 0


def test_a_provider_cannot_pay_their_own_mission(db, gateway):
    refused("provider_is_client", lambda: pay(db, client=CLIENT_ID, provider=CLIENT_ID))


@pytest.mark.parametrize("phone,operator,code", [("0810000000", "mpesa", "invalid_phone"), (PHONE, "africell", "invalid_operator")])
def test_phone_and_operator_are_checked(db, gateway, phone, operator, code):
    refused(code, lambda: mobile_money.create_intent(db, 1, phone=phone, operator=operator, funding_request=request()))


# --- Retraits -----------------------------------------------------------------------


def earn(db, gateway, amount=100.0):
    """Le prestataire gagne le net d'une mission (90 % du montant)."""
    pay(db, amount=amount)
    ledger.start_mission(db, 1, PROVIDER_ID)
    ledger.finish_mission(db, 1, PROVIDER_ID)
    ledger.confirm_completion(db, 1, CLIENT_ID)


def withdraw(db, amount=50.0, telegram_id=PROVIDER_ID):
    return mobile_money.request_payout(db, telegram_id=telegram_id, amount=amount, currency="USD", phone=PHONE, operator="airtel")


def test_a_payout_holds_the_money_and_waits_for_the_admin(db, gateway):
    earn(db, gateway)
    payout = withdraw(db)

    assert payout.status == "awaiting_approval"
    assert payout.needs_review_reason == "above_auto_limit"
    assert wallet(db, PROVIDER_ID) == money(40)  # 90 - 50 bloqués
    assert balance(db, ledger.PAYOUT_PENDING, payout.id) == money(50)
    assert gateway.payout_requests == 0  # rien n'est envoyé sans l'admin


def test_approved_payout_is_sent_and_the_provider_pays_the_fee(db, gateway, monkeypatch):
    monkeypatch.setenv("PAYOUT_FEE_RATE", "0.02")
    earn(db, gateway)
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)

    assert payout.status == "succeeded"
    assert payout.fee == money(1)
    assert balance(db, ledger.PAYOUT_PENDING, payout.id) == 0
    assert balance(db, ledger.FEES) == money("3.50")  # 2,50 d'encaissement + 1,00 de retrait
    assert wallet(db, PROVIDER_ID) == money(40)
    assert_books_balanced(db)


def test_rejected_or_failed_payouts_give_the_money_back(db, gateway):
    earn(db, gateway)
    mobile_money.reject_payout(db, withdraw(db, 30).id, ADMIN_ID, "doute")
    assert wallet(db, PROVIDER_ID) == money(90)

    gateway.payout = "failed"
    assert mobile_money.approve_payout(db, withdraw(db, 30).id, ADMIN_ID).status == "failed"
    assert wallet(db, PROVIDER_ID) == money(90)
    assert_books_balanced(db)


def test_a_payout_lost_in_transit_is_never_given_back_or_resent(db, gateway):
    earn(db, gateway)
    gateway.down = True
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)

    assert payout.status == "processing"
    assert wallet(db, PROVIDER_ID) == money(40)  # toujours bloqué, pas rendu
    gateway.down = False
    assert mobile_money.refresh_payout(db, payout.id).status == "succeeded"
    assert gateway.payout_requests == 1  # relu, pas renvoyé


def test_two_payouts_can_never_exceed_the_balance(db, gateway):
    earn(db, gateway)
    withdraw(db, 60)
    refused("insufficient_balance", lambda: withdraw(db, 60))
    db.rollback()
    assert wallet(db, PROVIDER_ID) == money(30)


def test_payouts_under_the_auto_limit_leave_without_the_admin(db, gateway, monkeypatch):
    monkeypatch.setenv("PAYOUT_AUTO_LIMIT_USD", "50")
    earn(db, gateway)

    assert withdraw(db, 50).status == "succeeded"
    assert withdraw(db, 30).status == "succeeded"
    assert withdraw(db, 5.0).status == "succeeded"
    assert wallet(db, PROVIDER_ID) == money(5)


def test_refund_money_needs_the_admin_even_under_the_auto_limit(db, gateway, monkeypatch):
    monkeypatch.setenv("PAYOUT_AUTO_LIMIT_USD", "1000")
    pay(db)
    ledger.open_dispute(db, 1, CLIENT_ID, "Travail non fait")
    ledger.resolve_dispute(db, 1, decision="refund", admin_telegram_id=ADMIN_ID)

    payout = withdraw(db, 50, telegram_id=CLIENT_ID)
    assert payout.status == "awaiting_approval"
    assert payout.needs_review_reason == "refund_funds"


@pytest.mark.parametrize("amount", [4.99, 0, -1])
def test_payout_minimum_and_invalid_amounts(db, gateway, amount):
    earn(db, gateway)
    with pytest.raises(ledger.MoneyError):
        withdraw(db, amount)
    db.rollback()
    assert wallet(db, PROVIDER_ID) == money(90)


def test_a_payout_is_decided_once(db, gateway):
    earn(db, gateway)
    payout = withdraw(db)
    mobile_money.approve_payout(db, payout.id, ADMIN_ID)
    mobile_money.approve_payout(db, payout.id, ADMIN_ID)  # double clic

    assert gateway.payout_requests == 1
    refused("invalid_state", lambda: mobile_money.reject_payout(db, payout.id, ADMIN_ID))
