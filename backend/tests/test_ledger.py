"""Règles d'argent du registre (backend/app/ledger.py).

Les classes de modèles viennent de `ledger` / `crud` eux-mêmes : d'autres
fichiers de tests rechargent `backend.app.models`, et mélanger deux
générations de classes dans une même session fausserait les lectures.
"""

import os
import threading
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend.app import crud, ledger

BotMission = ledger.BotMission
BotUser = crud.BotUser
BotQuote = crud.BotQuote
BotProvider = crud.BotProvider
LedgerEntry = ledger.LedgerEntry
MoneyOperation = ledger.MoneyOperation

CLIENT_ID = 42
PROVIDER_ID = 7

def acc(db, telegram_id):
    """Compte Nexis d'une personne connue par Telegram (créé au besoin)."""
    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)



@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    LedgerEntry.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    session.add(BotUser(telegram_id=CLIENT_ID, first_name="Client"))
    session.add(BotProvider(telegram_id=PROVIDER_ID, full_name="Prestataire"))
    session.commit()
    yield session
    session.close()
    engine.dispose()


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def accepted_quote(db, mission_id=1, amount=100.0, currency="USD", urgent=False, quote_ref=5, client=CLIENT_ID, provider_account=None, status="accepted"):
    """Mission du client CLIENT_ID et son devis accepté de PROVIDER_ID, tels
    que le backend les a enregistrés : ce que le paiement relit. Le devis
    porte le numéro `quote_ref` quand il est libre (références stables)."""
    mission = db.get(BotMission, mission_id)
    if mission is None:
        mission = BotMission(
            mission_id=mission_id, telegram_id=client, client_account_id=acc(db, client),
            service="service_plomberie", commune="Gombe", currency=currency, urgent=urgent, status="confirmed",
        )
        db.add(mission)
        db.flush()
    quote = db.get(BotQuote, quote_ref)
    provider_account = provider_account or acc(db, PROVIDER_ID)
    if (
        quote is None or quote.mission_id != mission_id or quote.amount != amount or quote.currency != currency
        or quote.provider_account_id != provider_account or quote.status != status
    ):
        quote = BotQuote(
            id=None if quote is not None else quote_ref, mission_id=mission_id, provider_telegram_id=PROVIDER_ID,
            provider_account_id=provider_account, amount=amount, currency=currency, delay_hours=2, status=status,
        )
        db.add(quote)
    db.commit()
    return quote.id


def fund(db, mission_id=1, method="mobile_money", amount=100.0, currency="USD", urgent=False, quote_ref=5, client=CLIENT_ID):
    quote_id = accepted_quote(db, mission_id, amount, currency, urgent, quote_ref)
    return ledger.fund_mission(db, mission_id, method=method, client_account_id=acc(db, client), quote_id=quote_id)


def new_mission(db, client=CLIENT_ID, key="demande-1", alert=()):
    """Mission créée par le backend ; renvoie le numéro qu'il lui donne."""
    mission, _ = crud.create_mission(
        db, channel=ledger.TELEGRAM, client_external_id=str(client), creation_key=key,
        service="service_plomberie", commune="Gombe", alert_provider_telegram_ids=list(alert),
        destination_latitude=-4.3076, destination_longitude=15.3125, destination_landmark="Portail bleu après la poste",
    )
    return mission.mission_id


def finished(db, mission_id=1, **kwargs):
    fund(db, mission_id, **kwargs)
    ledger.start_mission(db, mission_id, acc(db, PROVIDER_ID))
    return ledger.finish_mission(db, mission_id, acc(db, PROVIDER_ID))


def disputed(db, mission_id=1, **kwargs):
    fund(db, mission_id, **kwargs)
    return ledger.open_dispute(db, mission_id, acc(db, CLIENT_ID), "Travail non fait")


def bal(db, account_type, account_id, currency="USD"):
    """Pour un client ou un prestataire, `account_id` est le telegram_id : on
    passe par son compte Nexis, comme le reste du système."""
    if account_type == ledger.WALLET:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, account_id)
        if account_id is None:
            return money(0)
    return ledger.balance(db, account_type, account_id, currency)


def open_wallet(db, telegram_id, amount, currency="USD"):
    account_id = ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)
    ledger.record_opening_balance(db, account_id, currency, amount)
    db.commit()


def assert_books_balanced(db):
    """Partie double : chaque opération, et le registre entier, somment à 0."""
    per_operation = db.query(LedgerEntry.operation_id, func.sum(LedgerEntry.amount)).group_by(LedgerEntry.operation_id).all()
    assert all(money(total) == 0 for _, total in per_operation), per_operation
    for currency in ledger.CURRENCIES:
        total = db.query(func.coalesce(func.sum(LedgerEntry.amount), 0)).filter(LedgerEntry.currency == currency).scalar()
        assert money(total) == 0


def operations(db, mission_id=1):
    return db.query(MoneyOperation).filter(MoneyOperation.mission_id == mission_id).all()


def refused(code, call):
    with pytest.raises(ledger.MoneyError) as error:
        call()
    assert error.value.code == code
    return error.value


# --- Montants ---------------------------------------------------------------


def test_commission_is_10_percent_or_15_percent_when_urgent_rounded_to_the_cent():
    assert ledger.payment_amounts(100, urgent=False) == {"total": money(100), "commission": money(10), "net": money(90)}
    assert ledger.payment_amounts(100, urgent=True)["commission"] == money(15)
    # 33.35 * 0.10 = 3.335 -> 3.34 (arrondi commercial, pas bancaire)
    assert ledger.payment_amounts("33.35", urgent=False) == {"total": money("33.35"), "commission": money("3.34"), "net": money("30.01")}


@pytest.mark.parametrize("amount", [0, -5, "abc", "NaN", "Infinity"])
def test_invalid_amounts_are_refused(amount):
    refused("invalid_amount", lambda: ledger.payment_amounts(amount, urgent=False))


# --- Paiement ---------------------------------------------------------------


def test_mobile_money_payment_moves_the_total_into_the_mission_escrow(db):
    mission = fund(db)

    assert mission.status == "confirmed"
    assert mission.payment_status == "paid_escrow"
    assert mission.provider_telegram_id == PROVIDER_ID
    assert mission.total_client == 100.0 and mission.net_provider == 90.0 and mission.commission_amount == 10.0
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert bal(db, ledger.EXTERNAL, None) == money(-100)
    funding = ledger.mission_money_state(db, 1)["funding"]
    assert funding["reference"] == "SIM-0005"
    assert funding["total"] == "100.00"
    assert_books_balanced(db)


def test_a_payment_never_creates_a_mission(db):
    refused("mission_not_found", lambda: ledger.fund_mission(db, 77, method="mobile_money", client_account_id=acc(db, CLIENT_ID), quote_id=5))
    db.rollback()

    assert db.get(BotMission, 77) is None
    assert operations(db) == []


def test_the_amount_paid_is_the_accepted_quote_and_nothing_else(db):
    """Le montant, la devise et le prestataire ne sont jamais fournis par le
    canal : ils sont relus dans le devis accepté enregistré par le backend."""
    quote_id = accepted_quote(db, amount=80.0, currency="CDF")
    ledger.fund_mission(db, 1, method="mobile_money", client_account_id=acc(db, CLIENT_ID), quote_id=quote_id)

    funding = ledger.mission_money_state(db, 1)["funding"]
    assert (funding["total"], funding["commission"], funding["net"]) == ("80.00", "8.00", "72.00")
    assert bal(db, ledger.ESCROW, 1, "CDF") == money(80)
    assert db.get(BotMission, 1).provider_account_id == acc(db, PROVIDER_ID)
    assert db.get(BotMission, 1).accepted_quote_ref == quote_id


@pytest.mark.parametrize("status", ["pending", "rejected", "expired"])
def test_only_an_accepted_quote_can_be_paid(db, status):
    quote_id = accepted_quote(db, status=status)
    refused("quote_not_accepted", lambda: ledger.fund_mission(db, 1, method="mobile_money", client_account_id=acc(db, CLIENT_ID), quote_id=quote_id))
    db.rollback()
    assert operations(db) == []


def test_a_quote_of_another_mission_cannot_pay_this_one(db):
    other_quote = accepted_quote(db, mission_id=2, quote_ref=6)
    accepted_quote(db, mission_id=1)
    refused("quote_not_found", lambda: ledger.fund_mission(db, 1, method="mobile_money", client_account_id=acc(db, CLIENT_ID), quote_id=other_quote))
    refused("quote_not_found", lambda: ledger.fund_mission(db, 1, method="mobile_money", client_account_id=acc(db, CLIENT_ID), quote_id=4242))
    db.rollback()
    assert operations(db) == []


def test_paying_twice_the_same_way_is_a_harmless_replay(db):
    fund(db)
    fund(db)

    assert len(operations(db)) == 1
    assert bal(db, ledger.ESCROW, 1) == money(100)


def test_a_different_second_payment_is_refused(db):
    fund(db)
    error = refused("already_paid", lambda: fund(db, amount=50))
    assert error.mission.mission_id == 1
    db.rollback()
    assert bal(db, ledger.ESCROW, 1) == money(100)


def test_wallet_payment_is_refused_when_the_balance_is_short_and_writes_nothing(db):
    open_wallet(db, CLIENT_ID, 99.99)

    refused("insufficient_balance", lambda: fund(db, mission_id=3, method="wallet"))
    db.rollback()

    assert db.get(BotMission, 3).payment_status in (None, "unpaid")
    assert operations(db, 3) == []
    assert bal(db, ledger.WALLET, CLIENT_ID) == money("99.99")


def test_wallet_payment_debits_the_client_wallet(db):
    open_wallet(db, CLIENT_ID, 250)

    fund(db, method="wallet")

    assert bal(db, ledger.WALLET, CLIENT_ID) == money(150)
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert ledger.mission_money_state(db, 1)["funding"]["reference"] == "WLT-0005"
    assert_books_balanced(db)


def test_currencies_are_separate_wallets(db):
    open_wallet(db, CLIENT_ID, 1000)

    refused("insufficient_balance", lambda: fund(db, method="wallet", amount=20000, currency="CDF"))


def test_only_the_mission_client_can_pay(db):
    mission_id = new_mission(db)
    refused("not_mission_client", lambda: fund(db, mission_id=mission_id, client=999))


@pytest.mark.parametrize("field,value,code", [("method", "cash", "invalid_method"), ("currency", "EUR", "invalid_currency")])
def test_unknown_method_or_currency_is_refused(db, field, value, code):
    refused(code, lambda: fund(db, **{field: value}))


def test_a_lost_race_on_the_same_phase_is_resolved_by_the_database(db):
    """Deux demandes simultanées sur une mission pas encore connue : aucun
    verrou de ligne ne les sépare, les deux passent les vérifications. La
    contrainte d'unicité (mission, phase) tranche à l'écriture : rejeu
    identique accepté, demande différente refusée, jamais deux paiements."""
    fund(db)
    funding = ledger.mission_operation(db, 1, ledger.FUNDING)

    def duplicate_funding():
        ledger._record(
            db,
            kind="fund_mobile_money",
            currency="USD",
            mission_id=1,
            phase=ledger.FUNDING,
            movements=[(ledger.EXTERNAL, None, money(-100)), (ledger.ESCROW, 1, money(100))],
        )

    ledger._write(db, 1, ledger.FUNDING, lambda operation: operation.id == funding.id, duplicate_funding)
    refused("already_paid", lambda: ledger._write(db, 1, ledger.FUNDING, lambda operation: False, duplicate_funding))

    assert len(operations(db)) == 1
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert_books_balanced(db)


# --- Déroulement ---------------------------------------------------------------


def test_mission_cannot_start_before_payment(db):
    mission_id = new_mission(db)
    db.get(BotMission, mission_id).provider_telegram_id = PROVIDER_ID
    db.commit()
    refused("not_paid", lambda: ledger.start_mission(db, mission_id, acc(db, PROVIDER_ID)))


def test_only_the_mission_provider_can_start_or_finish(db):
    fund(db)
    refused("not_mission_provider", lambda: ledger.start_mission(db, 1, acc(db, 999)))
    ledger.start_mission(db, 1, acc(db, PROVIDER_ID))
    refused("not_mission_provider", lambda: ledger.finish_mission(db, 1, acc(db, 999)))


def test_mission_must_start_before_it_finishes(db):
    fund(db)
    refused("invalid_state", lambda: ledger.finish_mission(db, 1, acc(db, PROVIDER_ID)))


def test_start_and_finish_are_idempotent(db):
    fund(db)
    ledger.start_mission(db, 1, acc(db, PROVIDER_ID))
    ledger.start_mission(db, 1, acc(db, PROVIDER_ID))
    ledger.finish_mission(db, 1, acc(db, PROVIDER_ID))
    assert ledger.finish_mission(db, 1, acc(db, PROVIDER_ID)).status == "awaiting_confirmation"


# --- Libération -----------------------------------------------------------------


def test_client_confirmation_pays_the_provider_net_and_the_platform_commission(db):
    finished(db, urgent=True)

    mission = ledger.confirm_completion(db, 1, acc(db, CLIENT_ID))

    assert (mission.status, mission.payment_status) == ("completed", "released")
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(85)
    assert bal(db, ledger.PLATFORM, None) == money(15)
    assert bal(db, ledger.ESCROW, 1) == money(0)
    assert db.get(BotProvider, PROVIDER_ID).total_missions == 1
    assert_books_balanced(db)


def test_confirming_twice_pays_once(db):
    finished(db)
    ledger.confirm_completion(db, 1, acc(db, CLIENT_ID))
    ledger.confirm_completion(db, 1, acc(db, CLIENT_ID))

    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(90)
    assert len(operations(db)) == 2


def test_client_cannot_confirm_before_the_provider_finishes(db):
    fund(db)
    refused("invalid_state", lambda: ledger.confirm_completion(db, 1, acc(db, CLIENT_ID)))


def test_only_the_mission_client_can_confirm(db):
    finished(db)
    refused("not_mission_client", lambda: ledger.confirm_completion(db, 1, acc(db, 999)))


def test_auto_release_waits_48_hours_after_the_end(db):
    finished(db)
    mission = db.get(BotMission, 1)
    assert mission.release_after == mission.status_changed_at + timedelta(hours=48)
    ended_at = mission.status_changed_at

    refused("invalid_state", lambda: ledger.auto_release(db, 1, now=ended_at + timedelta(hours=47, minutes=59)))
    assert bal(db, ledger.ESCROW, 1) == money(100)

    assert ledger.auto_release(db, 1, now=ended_at + timedelta(hours=48)).payment_status == "released"
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(90)
    assert bal(db, ledger.ESCROW, 1) == money(0)


def test_auto_release_follows_the_recorded_deadline_not_the_current_rule(db):
    """Une mission terminée sous l'ancienne règle (échéance à 24 h, posée par
    la migration) est versée à son échéance, pas 48 h après."""
    finished(db)
    mission = db.get(BotMission, 1)
    mission.release_after = mission.status_changed_at + timedelta(hours=24)
    db.commit()

    assert ledger.auto_release(db, 1, now=mission.status_changed_at + timedelta(hours=24)).payment_status == "released"


def test_auto_release_never_pays_without_a_recorded_deadline(db):
    finished(db)
    mission = db.get(BotMission, 1)
    mission.release_after = None
    db.commit()

    refused("invalid_state", lambda: ledger.auto_release(db, 1, now=mission.status_changed_at + timedelta(days=30)))
    assert bal(db, ledger.ESCROW, 1) == money(100)


def test_a_repeated_finish_keeps_the_first_deadline(db):
    finished(db)
    deadline = db.get(BotMission, 1).release_after

    ledger.finish_mission(db, 1, acc(db, PROVIDER_ID))

    assert db.get(BotMission, 1).release_after == deadline


# --- Litige ---------------------------------------------------------------------


def test_dispute_freezes_the_escrow(db):
    finished(db)
    mission = ledger.open_dispute(db, 1, acc(db, CLIENT_ID), "  Travail non fait  ")

    assert mission.status == "disputed"
    assert mission.dispute_reason == "Travail non fait"
    assert mission.dispute_deadline - mission.dispute_opened_at == timedelta(hours=48)

    mission.status_changed_at = mission.status_changed_at - timedelta(days=10)
    db.commit()
    refused("mission_disputed", lambda: ledger.confirm_completion(db, 1, acc(db, CLIENT_ID)))
    refused("mission_disputed", lambda: ledger.auto_release(db, 1, now=mission.release_after + timedelta(days=10)))
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(0)


def test_dispute_can_be_opened_from_any_unsettled_paid_state(db):
    fund(db, mission_id=1)
    assert ledger.open_dispute(db, 1, acc(db, CLIENT_ID), "x").status == "disputed"
    fund(db, mission_id=2, quote_ref=6)
    ledger.start_mission(db, 2, acc(db, PROVIDER_ID))
    assert ledger.open_dispute(db, 2, acc(db, CLIENT_ID), "x").status == "disputed"
    finished(db, mission_id=3, quote_ref=7)
    assert ledger.open_dispute(db, 3, acc(db, CLIENT_ID), "x").status == "disputed"


def test_dispute_is_refused_before_payment_after_settlement_or_for_another_client(db):
    unpaid = new_mission(db)
    refused("not_paid", lambda: ledger.open_dispute(db, unpaid, acc(db, CLIENT_ID), "x"))

    paid = unpaid + 1
    finished(db, mission_id=paid)
    refused("not_mission_client", lambda: ledger.open_dispute(db, paid, acc(db, 999), "x"))
    ledger.confirm_completion(db, paid, acc(db, CLIENT_ID))
    refused("already_settled", lambda: ledger.open_dispute(db, paid, acc(db, CLIENT_ID), "x"))


@pytest.mark.parametrize("reason", ["", "   ", "x" * 1001])
def test_dispute_needs_a_reason(db, reason):
    fund(db)
    refused("invalid_reason", lambda: ledger.open_dispute(db, 1, acc(db, CLIENT_ID), reason))


# --- Décision de litige en deux temps, contestation, révision ----------------

ADMIN_ID = 900
OTHER_ADMIN_ID = 901
STRANGER_ID = 555


def decide(db, decision="refund", percentage=None, admin=ADMIN_ID, mission_id=1, now=None):
    return ledger.decide_dispute(
        db,
        mission_id,
        decision=decision,
        admin_account_id=acc(db, admin),
        admin_telegram_id=admin,
        provider_percentage=percentage,
        now=now,
    )


def first_decision(db, mission_id=1):
    return next(row for row in ledger.dispute_decisions(db, mission_id) if row.round == ledger.FIRST_DECISION)


def execute_when_due(db, mission_id=1):
    row = first_decision(db, mission_id)
    return ledger.execute_dispute_decision(db, row.id, now=row.execute_after)


def settle_dispute(db, decision="refund", percentage=None, mission_id=1):
    """Litige tranché puis exécuté à la fin du délai de contestation."""
    decide(db, decision, percentage, mission_id=mission_id)
    return execute_when_due(db, mission_id)


def contest(db, who=CLIENT_ID, reason="Le travail n'est pas fini", mission_id=1, now=None):
    return ledger.contest_dispute_decision(db, mission_id, acc(db, who), reason, now=now)


def test_a_decision_moves_no_money_for_three_days(db):
    disputed(db)

    mission = decide(db, "refund")

    row = first_decision(db)
    assert mission.status == "disputed"
    assert row.execute_after - row.decided_at == timedelta(days=3)
    assert (row.provider_amount, row.client_amount, row.platform_amount) == (money(0), money(100), money(0))
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(0)
    assert ledger.mission_operation(db, 1, ledger.SETTLEMENT) is None
    assert ledger.mission_money_state(db, 1)["dispute_decisions"][0]["state"] == "pending"
    refused(
        "decision_not_due",
        lambda: ledger.execute_dispute_decision(db, row.id, now=row.execute_after - timedelta(seconds=1)),
    )
    assert bal(db, ledger.ESCROW, 1) == money(100)


def test_full_refund_returns_everything_to_the_client_fees_included(db):
    disputed(db)

    mission = settle_dispute(db, "refund")

    assert (mission.status, mission.payment_status) == ("cancelled", "refunded")
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(100)
    assert bal(db, ledger.PLATFORM, None) == money(0)
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(0)
    assert_books_balanced(db)


def test_admin_release_pays_the_provider_like_a_confirmation(db):
    disputed(db)

    mission = settle_dispute(db, "release")

    assert (mission.status, mission.payment_status) == ("completed", "released")
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(90)
    assert bal(db, ledger.PLATFORM, None) == money(10)


@pytest.mark.parametrize(
    "percentage,provider,platform,client",
    [
        (50, "45.00", "5.00", "50.00"),
        (0, "0.00", "0.00", "100.00"),
        (100, "90.00", "10.00", "0.00"),
        ("33.33", "30.00", "3.33", "66.67"),
        (12.5, "11.25", "1.25", "87.50"),
    ],
)
def test_split_is_prorata_and_the_client_gets_the_rest_fees_included(db, percentage, provider, platform, client):
    """Partage au prorata (Ben, 2026-11-08) : le prestataire reçoit son net ×
    p, Nexis Hub garde sa commission × p, le client récupère le reste."""
    disputed(db)

    mission = settle_dispute(db, "split", percentage)

    assert (mission.status, mission.payment_status) == ("completed", "split")
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(provider)
    assert bal(db, ledger.PLATFORM, None) == money(platform)
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(client)
    assert bal(db, ledger.ESCROW, 1) == money(0)
    settlement = ledger.mission_money_state(db, 1)["settlement"]
    assert (settlement["provider_amount"], settlement["platform_amount"], settlement["client_amount"]) == (provider, platform, client)
    assert_books_balanced(db)


def test_split_rounding_never_loses_or_creates_a_cent(db):
    """Montant urgent qui ne tombe pas rond : chaque part est arrondie au
    centime et le client reçoit exactement le reste."""
    disputed(db, amount=33.33, urgent=True)

    settle_dispute(db, "split", "33.33")

    # Total 33.33, commission 15 % = 5.00, net 28.33.
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money("9.44")
    assert bal(db, ledger.PLATFORM, None) == money("1.67")
    assert bal(db, ledger.WALLET, CLIENT_ID) == money("22.22")
    assert bal(db, ledger.ESCROW, 1) == money(0)
    assert_books_balanced(db)


def test_the_executed_amounts_are_the_ones_frozen_at_decision_time(db):
    disputed(db)
    decide(db, "split", 40)
    frozen = ledger.mission_money_state(db, 1)["dispute_decisions"][0]

    execute_when_due(db)

    settlement = ledger.mission_money_state(db, 1)["settlement"]
    assert (settlement["provider_amount"], settlement["client_amount"], settlement["platform_amount"]) == (
        frozen["provider_amount"],
        frozen["client_amount"],
        frozen["platform_amount"],
    )
    row = first_decision(db)
    assert row.executed_operation_id == ledger.mission_operation(db, 1, ledger.SETTLEMENT).id
    assert ledger.mission_money_state(db, 1)["dispute_decisions"][0]["state"] == "executed"


@pytest.mark.parametrize("percentage", [-1, 100.01, "abc", None, float("nan")])
def test_split_refuses_an_invalid_percentage(db, percentage):
    disputed(db)
    refused("invalid_percentage", lambda: decide(db, "split", percentage))
    assert ledger.dispute_decisions(db, 1) == []


def test_a_decision_is_recorded_once_and_executed_once(db):
    disputed(db)
    decide(db, "split", 50)
    decide(db, "split", 50)  # rejeu (double clic)
    refused("decision_pending", lambda: decide(db, "refund"))
    refused("decision_pending", lambda: decide(db, "split", 60))
    refused("decision_pending", lambda: decide(db, "refund", admin=OTHER_ADMIN_ID))
    assert len(ledger.dispute_decisions(db, 1)) == 1

    execute_when_due(db)
    execute_when_due(db)  # la tâche repasse : rien de plus
    decide(db, "split", 50)  # rejeu après exécution : état enregistré
    refused("already_settled", lambda: decide(db, "refund", admin=OTHER_ADMIN_ID))

    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(45)
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(50)
    assert db.query(MoneyOperation).filter(MoneyOperation.phase == ledger.SETTLEMENT).count() == 1


def test_only_a_disputed_mission_can_be_decided(db):
    fund(db)
    refused("not_disputed", lambda: decide(db, "refund"))
    refused("invalid_decision", lambda: decide(db, "cancel"))


@pytest.mark.parametrize("who", [CLIENT_ID, PROVIDER_ID])
def test_the_client_or_the_provider_can_contest_before_execution(db, who):
    disputed(db)
    decide(db, "release")
    row = first_decision(db)
    contested_at = row.execute_after - timedelta(minutes=1)

    mission = contest(db, who, now=contested_at)

    row = first_decision(db)
    assert mission.status == "disputed"
    assert row.contested_at == contested_at
    assert row.contested_by_role == ("client" if who == CLIENT_ID else "provider")
    # Nouveau délai de réponse pour la révision, avec ses alertes.
    assert mission.dispute_deadline == contested_at + ledger.DISPUTE_REVIEW_DELAY
    assert mission.dispute_overdue_alerted_at is None
    refused("decision_contested", lambda: ledger.execute_dispute_decision(db, row.id, now=row.execute_after + timedelta(days=1)))
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert ledger.mission_money_state(db, 1)["dispute_decisions"][0]["state"] == "contested"


def test_a_decision_is_contested_once(db):
    disputed(db)
    decide(db, "refund")
    contest(db, PROVIDER_ID)
    contest(db, PROVIDER_ID)  # rejeu
    refused("already_contested", lambda: contest(db, CLIENT_ID))


def test_only_the_parties_can_contest(db):
    disputed(db)
    decide(db, "refund")
    refused("not_mission_party", lambda: contest(db, STRANGER_ID))
    refused("not_mission_party", lambda: contest(db, ADMIN_ID))
    assert first_decision(db).contested_at is None


def test_no_contest_after_the_three_days_or_after_execution(db):
    disputed(db)
    decide(db, "refund")
    row = first_decision(db)
    refused("contest_window_closed", lambda: contest(db, PROVIDER_ID, now=row.execute_after))

    ledger.execute_dispute_decision(db, row.id, now=row.execute_after)
    refused("decision_already_executed", lambda: contest(db, PROVIDER_ID, now=row.decided_at))


def test_no_contest_without_a_decision_or_without_a_reason(db):
    disputed(db)
    refused("no_decision", lambda: contest(db, PROVIDER_ID))
    decide(db, "refund")
    refused("invalid_reason", lambda: contest(db, PROVIDER_ID, reason="   "))
    refused("invalid_reason", lambda: contest(db, PROVIDER_ID, reason="x" * (ledger.MAX_DISPUTE_REASON_LENGTH + 1)))


def test_the_review_must_come_from_another_person_and_is_final(db):
    disputed(db)
    decide(db, "release")
    contest(db, CLIENT_ID)

    refused("same_reviewer", lambda: decide(db, "refund", admin=ADMIN_ID))
    assert bal(db, ledger.ESCROW, 1) == money(100)

    mission = decide(db, "split", 50, admin=OTHER_ADMIN_ID)

    assert (mission.status, mission.payment_status) == ("completed", "split")
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(45)
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(50)
    rounds = ledger.mission_money_state(db, 1)["dispute_decisions"]
    assert [(view["round"], view["state"]) for view in rounds] == [(1, "contested"), (2, "executed")]
    settlement = ledger.mission_money_state(db, 1)["settlement"]
    assert settlement["decision_round"] == 2

    decide(db, "split", 50, admin=OTHER_ADMIN_ID)  # rejeu de la révision
    refused("already_settled", lambda: decide(db, "refund", admin=OTHER_ADMIN_ID))
    refused("already_contested", lambda: contest(db, PROVIDER_ID))
    assert_books_balanced(db)


def test_with_a_single_admin_a_contested_decision_stays_frozen(db):
    """Tant qu'une deuxième personne n'existe pas, la révision est impossible
    et l'argent reste gelé : jamais d'exécution par défaut."""
    disputed(db)
    decide(db, "release")
    row = first_decision(db)
    contest(db, CLIENT_ID)

    refused("same_reviewer", lambda: decide(db, "release"))
    refused("decision_contested", lambda: ledger.execute_dispute_decision(db, row.id, now=row.execute_after + timedelta(days=30)))
    assert bal(db, ledger.ESCROW, 1) == money(100)


def _in_parallel(backend_db_url, *calls):
    """Lance chaque appel dans sa propre session, au même instant, et renvoie
    pour chacun le résultat ou le code du refus."""
    engine = create_engine(backend_db_url, future=True)
    barrier = threading.Barrier(len(calls))
    results = [None] * len(calls)

    def run(index, call):
        session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
        try:
            barrier.wait()
            call(session)
            results[index] = "ok"
        except ledger.MoneyError as error:
            session.rollback()
            results[index] = error.code
        finally:
            session.close()

    threads = [threading.Thread(target=run, args=(index, call)) for index, call in enumerate(calls)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    engine.dispose()
    return results


postgres_only = pytest.mark.skipif(
    os.getenv("NEXIS_TEST_BACKEND_DB", "sqlite") != "postgres",
    reason="Verrous FOR UPDATE : à vérifier sur Postgres",
)


@postgres_only
def test_two_simultaneous_executions_settle_once(db, backend_db_url):
    disputed(db)
    decide(db, "split", 50)
    row = first_decision(db)

    def execute(session):
        ledger.execute_dispute_decision(session, row.id, now=row.execute_after)

    assert _in_parallel(backend_db_url, execute, execute) == ["ok", "ok"]
    db.expire_all()
    assert db.query(MoneyOperation).filter(MoneyOperation.phase == ledger.SETTLEMENT).count() == 1
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(45)
    assert_books_balanced(db)


@postgres_only
def test_a_contest_and_the_execution_at_the_same_time_only_one_wins(db, backend_db_url):
    disputed(db)
    decide(db, "release")
    row = first_decision(db)
    client_account = acc(db, CLIENT_ID)

    def execute(session):
        ledger.execute_dispute_decision(session, row.id, now=row.execute_after)

    def contest_now(session):
        ledger.contest_dispute_decision(session, 1, client_account, "Pas d'accord", now=row.execute_after - timedelta(seconds=1))

    executed, contested = _in_parallel(backend_db_url, execute, contest_now)

    db.expire_all()
    settled = ledger.mission_operation(db, 1, ledger.SETTLEMENT) is not None
    if settled:
        assert (executed, contested) == ("ok", "decision_already_executed")
        assert first_decision(db).contested_at is None
    else:
        assert (executed, contested) == ("decision_contested", "ok")
        assert bal(db, ledger.ESCROW, 1) == money(100)


def test_wallet_refund_can_pay_a_later_mission(db):
    disputed(db)
    settle_dispute(db, "refund")

    fund(db, mission_id=2, method="wallet", quote_ref=8)

    assert bal(db, ledger.WALLET, CLIENT_ID) == money(0)
    assert bal(db, ledger.ESCROW, 2) == money(100)
    assert_books_balanced(db)


def test_wallets_belong_to_a_channel_neutral_nexis_account(db):
    """Le registre ne connaît que des comptes Nexis : un futur canal (WhatsApp)
    rattaché au même compte voit le même wallet, sans rien migrer."""
    disputed(db)
    settle_dispute(db, "refund")

    account_id = ledger.account_id_for(db, ledger.TELEGRAM, CLIENT_ID)
    db.add(ledger.ChannelIdentity(account_id=account_id, channel="whatsapp", external_id="+243810000000"))
    db.commit()

    assert ledger.wallet_balances(db, ledger.account_id_for(db, "whatsapp", "+243810000000"))["USD"] == money(100)
    entries = db.query(LedgerEntry).filter(LedgerEntry.account_type == ledger.WALLET).all()
    assert {entry.account_id for entry in entries} == {account_id}
    assert db.get(BotMission, 1).client_account_id == account_id


def test_one_person_has_a_single_wallet_whether_client_or_provider(db):
    """Le prestataire 7 commande à son tour comme client : son wallet est le
    même, il peut payer avec ce qu'il a gagné."""
    finished(db)
    ledger.confirm_completion(db, 1, acc(db, CLIENT_ID))
    db.add(BotUser(telegram_id=PROVIDER_ID, first_name="Prestataire"))
    db.commit()

    quote_id = accepted_quote(db, mission_id=2, amount=40.0, quote_ref=9, client=PROVIDER_ID, provider_account=acc(db, CLIENT_ID))
    ledger.fund_mission(db, 2, method="wallet", client_account_id=acc(db, PROVIDER_ID), quote_id=quote_id)

    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(50)


def test_a_provider_can_never_be_paid_for_their_own_mission(db):
    quote_id = accepted_quote(db, amount=10.0, quote_ref=1, provider_account=acc(db, CLIENT_ID))
    refused(
        "provider_is_client",
        lambda: ledger.fund_mission(db, 1, method="mobile_money", client_account_id=acc(db, CLIENT_ID), quote_id=quote_id),
    )
    db.rollback()
    assert db.query(MoneyOperation).count() == 0


# --- Règles par compte Nexis ---------------------------------------------------


def test_mission_rules_compare_accounts_not_telegram_ids(db):
    """Seuls les comptes comptent : un autre compte est refusé même si la
    mission garde l'ancien identifiant Telegram de la personne."""
    fund(db)
    intruder = acc(db, 999)
    refused("not_mission_provider", lambda: ledger.start_mission(db, 1, intruder))
    refused("not_mission_client", lambda: ledger.open_dispute(db, 1, intruder, "x"))
    assert ledger.start_mission(db, 1, acc(db, PROVIDER_ID)).status == "in_progress"


def test_a_mission_without_linked_accounts_is_refused_never_accepted(db):
    """Historique mal rattaché : refus explicite, jamais d'action par défaut."""
    finished(db)
    mission = db.get(BotMission, 1)
    mission.client_account_id = None
    mission.provider_account_id = None
    db.commit()

    refused("mission_account_missing", lambda: ledger.confirm_completion(db, 1, acc(db, CLIENT_ID)))
    refused("mission_account_missing", lambda: ledger.open_dispute(db, 1, acc(db, CLIENT_ID), "x"))
    refused("mission_account_missing", lambda: ledger.finish_mission(db, 1, acc(db, PROVIDER_ID)))
    assert db.get(BotMission, 1).payment_status == "paid_escrow"
    assert_books_balanced(db)


def test_a_provider_without_account_cannot_be_paid(db):
    client_account = acc(db, CLIENT_ID)
    unknown = ledger.NexisAccount()
    db.add(unknown)
    db.commit()  # compte sans identité Telegram : pas un prestataire
    quote_id = accepted_quote(db, amount=10.0, quote_ref=1, provider_account=unknown.id)
    refused(
        "provider_not_found",
        lambda: ledger.fund_mission(db, 1, method="mobile_money", client_account_id=client_account, quote_id=quote_id),
    )
    db.rollback()
    assert operations(db) == []


def test_money_operations_record_the_acting_account(db):
    finished(db)
    ledger.confirm_completion(db, 1, acc(db, CLIENT_ID))
    by_phase = {operation.phase: operation for operation in operations(db)}
    assert by_phase["funding"].actor_account_id == acc(db, CLIENT_ID)
    assert by_phase["settlement"].actor_account_id == acc(db, CLIENT_ID)
    assert by_phase["funding"].actor_telegram_id == CLIENT_ID


def test_a_payment_recorded_before_accounts_is_still_recognised_as_a_replay(db):
    """Un paiement enregistré avec l'ancien format (prestataire nommé par son
    identifiant Telegram) : le même paiement rejoué n'est ni refusé ni doublé."""
    fund(db)
    funding = next(operation for operation in operations(db) if operation.phase == "funding")
    legacy = dict(funding.details)
    legacy["provider_telegram_id"] = PROVIDER_ID
    del legacy["provider_account_id"]
    funding.details = legacy
    db.commit()

    assert fund(db).payment_status == "paid_escrow"
    assert len(operations(db)) == 1
    refused("already_paid", lambda: fund(db, amount=50))
