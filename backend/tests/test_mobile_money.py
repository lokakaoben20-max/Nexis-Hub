"""Paiements et retraits Mobile Money (backend/app/mobile_money.py), avec un
agrégateur de test dont on règle chaque réponse.

Classes prises dans `ledger` / `crud` : voir test_ledger.py.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend.app import ledger, mobile_money, reconciliation
from backend.tests import profils_de_test
from backend.tests.test_ledger import accepted_quote
from backend.app.payment_gateway import FAILED, NOT_FOUND, PENDING, SUCCEEDED, GatewayResult, GatewayUnavailable

LedgerEntry = ledger.LedgerEntry
PaymentIntent = mobile_money.PaymentIntent
Payout = mobile_money.Payout
CLIENT_ID, PROVIDER_ID, ADMIN_ID = 42, 7, 1
PHONE = "+243810000000"

def acc(db, telegram_id):
    """Compte Nexis d'une personne connue par Telegram (créé au besoin)."""
    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)



class FakeGateway:
    """Agrégateur de test qui se comporte comme le vrai contrat
    (`payment_gateway`) : il retient chaque transaction par notre référence,
    refuse un second ordre qui la porte, et dit `NOT_FOUND` pour une
    référence qu'il n'a jamais reçue. `collection` / `payout` disent comment
    il répondra.

    Pannes réglables :
    - `down` : il ne répond pas, et la demande ne lui parvient pas ;
    - `lose_answer` : la demande lui parvient, mais sa réponse se perd ;
    - `drop_requests` : les demandes se perdent en route, la lecture du
      statut marche.
    """

    name = "fake"

    def __init__(self):
        self.collection = "succeeded"
        self.amount = None
        self.fee = Decimal("2.50")
        self.payout = "succeeded"
        self.down = False
        self.lose_answer = False
        self.drop_requests = False
        self.payout_requests = 0  # ordres de versement reçus, doublons compris
        self.duplicates_refused = 0
        self.known = {}  # notre référence -> sa référence

    def _check(self):
        if self.down:
            raise GatewayUnavailable()

    def _receive(self, reference, gateway_reference):
        if self.drop_requests:
            raise GatewayUnavailable()
        if reference in self.known:
            self.duplicates_refused += 1
            return
        self.known[reference] = gateway_reference

    def _answer(self):
        if self.lose_answer:
            raise GatewayUnavailable()

    def request_collection(self, intent):
        self._check()
        self._receive(intent.reference, f"FAKE-{intent.id}")
        self._answer()
        return self.collection_status(intent)

    def collection_status(self, intent):
        self._check()
        if intent.reference not in self.known:
            return GatewayResult(NOT_FOUND)
        status = {"succeeded": SUCCEEDED, "pending": PENDING, "failed": FAILED}[self.collection]
        amount = self.amount if self.amount is not None else intent.amount
        return GatewayResult(status, self.known[intent.reference], Decimal(amount), intent.currency, self.fee, "refusé" if status == FAILED else None)

    def request_payout(self, payout):
        self.payout_requests += 1
        self._check()
        self._receive(payout.reference, f"FAKE-OUT-{payout.id}")
        self._answer()
        return self.payout_status(payout)

    def payout_status(self, payout):
        self._check()
        if payout.reference not in self.known:
            return GatewayResult(NOT_FOUND)
        status = {"succeeded": SUCCEEDED, "pending": PENDING, "failed": FAILED}[self.payout]
        return GatewayResult(status, self.known[payout.reference])

    def forget(self, reference):
        """L'agrégateur perd une transaction qu'il avait acceptée."""
        del self.known[reference]


@pytest.fixture
def gateway(monkeypatch):
    fake = FakeGateway()
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: fake)
    return fake


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    LedgerEntry.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    profils_de_test.client(session, CLIENT_ID)
    profils_de_test.provider(session, PROVIDER_ID)
    session.commit()
    yield session
    session.close()
    engine.dispose()


def money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"))


def pay(db, mission_id=1, amount=100.0, quote_ref=5, client=CLIENT_ID, provider=PROVIDER_ID):
    """Intention de paiement sur le devis accepté de la mission (montant et
    prestataire relus dans le backend)."""
    quote_id = accepted_quote(db, mission_id, amount=amount, quote_ref=quote_ref, provider_account=acc(db, provider))
    return mobile_money.create_intent(
        db, mission_id, phone=PHONE, operator="mpesa", client_account_id=acc(db, client), quote_id=quote_id
    )


def wallet(db, telegram_id, currency="USD"):
    return ledger.wallet_balances(db, acc(db, telegram_id))[currency]


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


def test_an_unreachable_aggregator_moves_nothing_and_keeps_the_intent_open(db, gateway):
    gateway.down = True
    intent = pay(db)

    assert intent.status == "created"  # on ne sait pas si la demande est arrivée
    assert db.query(ledger.MoneyOperation).count() == 0
    assert pay(db).id == intent.id  # aucune seconde demande tant qu'on ne sait pas


def test_a_provider_cannot_pay_their_own_mission(db, gateway):
    refused("provider_is_client", lambda: pay(db, client=CLIENT_ID, provider=CLIENT_ID))


@pytest.mark.parametrize("phone,operator,code", [("0810000000", "mpesa", "invalid_phone"), (PHONE, "africell", "invalid_operator")])
def test_phone_and_operator_are_checked(db, gateway, phone, operator, code):
    quote_id = accepted_quote(db)
    refused(code, lambda: mobile_money.create_intent(db, 1, phone=phone, operator=operator, client_account_id=acc(db, CLIENT_ID), quote_id=quote_id))


# --- Retraits -----------------------------------------------------------------------


def earn(db, gateway, amount=100.0):
    """Le prestataire gagne le net d'une mission (90 % du montant)."""
    pay(db, amount=amount)
    ledger.start_mission(db, 1, acc(db, PROVIDER_ID))
    ledger.finish_mission(db, 1, acc(db, PROVIDER_ID))
    ledger.confirm_completion(db, 1, acc(db, CLIENT_ID))


def withdraw(db, amount=50.0, telegram_id=PROVIDER_ID):
    return mobile_money.request_payout(db, account_id=acc(db, telegram_id), amount=amount, currency="USD", phone=PHONE, operator="airtel")


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
    gateway.lose_answer = True  # l'ordre arrive, la réponse se perd
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)
    gateway.lose_answer = False

    assert payout.status == "processing"
    assert wallet(db, PROVIDER_ID) == money(40)  # toujours bloqué, pas rendu
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
    ledger.open_dispute(db, 1, acc(db, CLIENT_ID), "Travail non fait")
    admin_account = acc(db, ADMIN_ID)
    ledger.decide_dispute(db, 1, decision="refund", admin_account_id=admin_account, admin_telegram_id=ADMIN_ID)
    decision = ledger.dispute_decisions(db, 1)[0]
    ledger.execute_dispute_decision(db, decision.id, now=decision.execute_after)

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


# --- Pannes : réponse perdue, demande jamais arrivée, agrégateur incohérent ---------
# Le backend ne conclut jamais d'un silence : il relit par notre référence.


def older(row, field, delta):
    setattr(row, field, getattr(row, field) - delta)


def test_every_intent_and_payout_carries_its_own_reference(db, gateway, monkeypatch):
    monkeypatch.setenv("PAYOUT_AUTO_LIMIT_USD", "1000")
    gateway.collection = "failed"
    first, second = pay(db), pay(db)
    gateway.collection = "succeeded"
    earn(db, gateway)
    payout = withdraw(db, 20)

    references = [first.reference, second.reference, payout.reference]
    assert first.reference.startswith("NXI") and payout.reference.startswith("NXO")
    assert all(len(reference) == 35 and reference.isalnum() for reference in references)
    assert len(set(references)) == 3
    assert set(references) <= set(gateway.known)  # c'est elle que l'agrégateur a reçue


def test_a_lost_answer_never_charges_the_client_twice(db, gateway):
    gateway.collection = "pending"
    gateway.lose_answer = True
    intent = pay(db)
    gateway.lose_answer = False

    assert intent.status == "created"
    assert pay(db).id == intent.id  # second clic : même intention, aucune autre demande
    assert len(gateway.known) == 1

    gateway.collection = "succeeded"  # le client a validé sur son téléphone
    assert mobile_money.refresh_intent(db, intent.id).status == "succeeded"
    assert balance(db, ledger.ESCROW, 1) == money(100)
    assert_books_balanced(db)


def test_a_request_that_never_arrived_fails_only_after_the_delay_then_can_be_retried(db, gateway):
    gateway.down = True
    intent = pay(db)
    gateway.down = False

    # Tout de suite : la demande pourrait encore être en route.
    assert mobile_money.refresh_intent(db, intent.id).status == "created"

    older(intent, "created_at", mobile_money.STALLED_CREATED_AFTER + timedelta(seconds=1))
    db.commit()
    intent = mobile_money.refresh_intent(db, intent.id)
    assert (intent.status, intent.failure_reason) == ("failed", "never_reached_gateway")
    assert db.query(ledger.MoneyOperation).count() == 0

    retry = pay(db)
    assert retry.id != intent.id and retry.reference != intent.reference
    assert retry.status == "succeeded"


def test_money_confirmed_after_a_failure_is_never_ignored(db, gateway):
    gateway.collection = "failed"
    intent = pay(db)
    assert intent.status == "failed"

    gateway.collection = "pending"  # un échec n'est jamais rouvert
    assert mobile_money.refresh_intent(db, intent.id).status == "failed"

    gateway.collection = "succeeded"  # webhook tardif : l'argent est arrivé quand même
    assert mobile_money.refresh_intent(db, intent.id).status == "succeeded"
    assert balance(db, ledger.ESCROW, 1) == money(100)
    assert_books_balanced(db)


def test_money_confirmed_after_a_failure_on_a_paid_mission_goes_to_the_wallet(db, gateway):
    gateway.collection = "failed"
    failed = pay(db)
    gateway.collection = "succeeded"
    assert pay(db).status == "succeeded"

    assert mobile_money.refresh_intent(db, failed.id).status == "overpaid"
    assert balance(db, ledger.ESCROW, 1) == money(100)  # jamais payée deux fois
    assert wallet(db, CLIENT_ID) == money(100)
    assert_books_balanced(db)


def test_an_intent_the_aggregator_forgets_is_flagged_never_failed(db, gateway):
    gateway.collection = "pending"
    intent = pay(db)
    gateway.forget(intent.reference)
    older(intent, "created_at", timedelta(hours=1))
    db.commit()

    intent = mobile_money.refresh_intent(db, intent.id)
    assert intent.status == "pending"  # le client a peut-être payé : on ne conclut rien
    assert intent.failure_reason == mobile_money.UNKNOWN_AT_GATEWAY
    report = reconciliation.reconcile(db, ledger._utcnow())
    assert "intent_unknown_at_gateway" in [anomaly["code"] for anomaly in report.anomalies]


def test_a_payout_that_never_arrived_is_resent_once_with_the_same_reference(db, gateway):
    earn(db, gateway)
    gateway.down = True
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)
    gateway.down = False
    assert (payout.status, payout.send_count) == ("processing", 1)

    # Trop tôt : la demande pourrait encore être en route.
    assert mobile_money.refresh_payout(db, payout.id).status == "processing"
    assert gateway.payout_requests == 1

    older(payout, "last_sent_at", mobile_money.PAYOUT_RESEND_AFTER + timedelta(seconds=1))
    db.commit()
    payout = mobile_money.refresh_payout(db, payout.id)
    assert (payout.status, payout.send_count) == ("succeeded", 2)
    assert payout.reference in gateway.known
    assert gateway.duplicates_refused == 0
    assert wallet(db, PROVIDER_ID) == money(40)
    assert balance(db, ledger.PAYOUT_PENDING, payout.id) == 0
    assert_books_balanced(db)


def test_a_payout_already_received_is_never_sent_twice(db, gateway):
    earn(db, gateway)
    gateway.payout = "pending"
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)

    # Double appel d'envoi (double clic, deux processus) : un seul ordre.
    assert mobile_money._send_payout(db, payout.id).send_count == 1
    older(payout, "last_sent_at", timedelta(hours=1))
    db.commit()
    mobile_money.refresh_payout(db, payout.id)  # l'agrégateur le connaît : relu, pas renvoyé

    assert gateway.payout_requests == 1
    assert db.get(Payout, payout.id).send_count == 1


def test_resends_stop_at_the_limit_and_the_admin_is_told(db, gateway):
    earn(db, gateway)
    gateway.drop_requests = True
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)
    for _ in range(mobile_money.MAX_PAYOUT_SENDS + 2):
        older(payout, "last_sent_at", mobile_money.PAYOUT_RESEND_AFTER + timedelta(seconds=1))
        db.commit()
        payout = mobile_money.refresh_payout(db, payout.id)

    assert gateway.payout_requests == mobile_money.MAX_PAYOUT_SENDS
    assert payout.status == "processing"
    assert wallet(db, PROVIDER_ID) == money(40)  # jamais rendu sur ce seul motif
    report = reconciliation.reconcile(db, ledger._utcnow())
    assert "payout_never_received" in [anomaly["code"] for anomaly in report.anomalies]
