"""Règles d'argent du registre (backend/app/ledger.py).

Les classes de modèles viennent de `ledger` / `crud` eux-mêmes : d'autres
fichiers de tests rechargent `backend.app.models`, et mélanger deux
générations de classes dans une même session fausserait les lectures.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker

from backend.app import crud, ledger

BotMission = ledger.BotMission
BotUser = ledger.BotUser
BotProvider = crud.BotProvider
LedgerEntry = ledger.LedgerEntry
MoneyOperation = ledger.MoneyOperation

CLIENT_ID = 42
PROVIDER_ID = 7


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}", future=True)
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


def fund(db, mission_id=1, method="mobile_money", amount=100.0, currency="USD", urgent=False, quote_ref=5, client=CLIENT_ID):
    return ledger.fund_mission(
        db,
        mission_id,
        method=method,
        client_telegram_id=client,
        provider_telegram_id=PROVIDER_ID,
        quote_ref=quote_ref,
        amount=amount,
        currency=currency,
        urgent=urgent,
        service="service_plomberie",
        commune="Gombe",
    )


def finished(db, mission_id=1, **kwargs):
    fund(db, mission_id, **kwargs)
    ledger.start_mission(db, mission_id, PROVIDER_ID)
    return ledger.finish_mission(db, mission_id, PROVIDER_ID)


def disputed(db, mission_id=1, **kwargs):
    fund(db, mission_id, **kwargs)
    return ledger.open_dispute(db, mission_id, CLIENT_ID, "Travail non fait")


def bal(db, account_type, account_id, currency="USD"):
    return ledger.balance(db, account_type, account_id, currency)


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


def test_payment_creates_the_mission_when_the_backend_never_received_it(db):
    fund(db, mission_id=77)

    assert db.get(BotMission, 77).telegram_id == CLIENT_ID
    assert db.get(BotUser, CLIENT_ID).total_missions == 1


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
    ledger.record_opening_balance(db, ledger.CLIENT, CLIENT_ID, "USD", 99.99)
    db.commit()

    refused("insufficient_balance", lambda: fund(db, mission_id=3, method="wallet"))
    db.rollback()

    assert db.get(BotMission, 3) is None
    assert operations(db, 3) == []
    assert bal(db, ledger.CLIENT, CLIENT_ID) == money("99.99")


def test_wallet_payment_debits_the_client_wallet(db):
    ledger.record_opening_balance(db, ledger.CLIENT, CLIENT_ID, "USD", 250)
    db.commit()

    fund(db, method="wallet")

    assert bal(db, ledger.CLIENT, CLIENT_ID) == money(150)
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert ledger.mission_money_state(db, 1)["funding"]["reference"] == "WLT-0005"
    assert_books_balanced(db)


def test_currencies_are_separate_wallets(db):
    ledger.record_opening_balance(db, ledger.CLIENT, CLIENT_ID, "USD", 1000)
    db.commit()

    refused("insufficient_balance", lambda: fund(db, method="wallet", amount=20000, currency="CDF"))


def test_only_the_mission_client_can_pay(db):
    crud.create_mission(db, CLIENT_ID, 1, "service_plomberie", "Gombe")
    refused("not_mission_client", lambda: fund(db, client=999))


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
    crud.create_mission(db, CLIENT_ID, 1, "service_plomberie", "Gombe")
    db.get(BotMission, 1).provider_telegram_id = PROVIDER_ID
    db.commit()
    refused("not_paid", lambda: ledger.start_mission(db, 1, PROVIDER_ID))


def test_only_the_mission_provider_can_start_or_finish(db):
    fund(db)
    refused("not_mission_provider", lambda: ledger.start_mission(db, 1, 999))
    ledger.start_mission(db, 1, PROVIDER_ID)
    refused("not_mission_provider", lambda: ledger.finish_mission(db, 1, 999))


def test_mission_must_start_before_it_finishes(db):
    fund(db)
    refused("invalid_state", lambda: ledger.finish_mission(db, 1, PROVIDER_ID))


def test_start_and_finish_are_idempotent(db):
    fund(db)
    ledger.start_mission(db, 1, PROVIDER_ID)
    ledger.start_mission(db, 1, PROVIDER_ID)
    ledger.finish_mission(db, 1, PROVIDER_ID)
    assert ledger.finish_mission(db, 1, PROVIDER_ID).status == "awaiting_confirmation"


# --- Libération -----------------------------------------------------------------


def test_client_confirmation_pays_the_provider_net_and_the_platform_commission(db):
    finished(db, urgent=True)

    mission = ledger.confirm_completion(db, 1, CLIENT_ID)

    assert (mission.status, mission.payment_status) == ("completed", "released")
    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(85)
    assert bal(db, ledger.PLATFORM, None) == money(15)
    assert bal(db, ledger.ESCROW, 1) == money(0)
    assert db.get(BotProvider, PROVIDER_ID).total_missions == 1
    assert_books_balanced(db)


def test_confirming_twice_pays_once(db):
    finished(db)
    ledger.confirm_completion(db, 1, CLIENT_ID)
    ledger.confirm_completion(db, 1, CLIENT_ID)

    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(90)
    assert len(operations(db)) == 2


def test_client_cannot_confirm_before_the_provider_finishes(db):
    fund(db)
    refused("invalid_state", lambda: ledger.confirm_completion(db, 1, CLIENT_ID))


def test_only_the_mission_client_can_confirm(db):
    finished(db)
    refused("not_mission_client", lambda: ledger.confirm_completion(db, 1, 999))


def test_auto_release_waits_24_hours(db):
    finished(db)
    refused("invalid_state", lambda: ledger.auto_release(db, 1))

    mission = db.get(BotMission, 1)
    mission.status_changed_at = mission.status_changed_at - timedelta(hours=25)
    db.commit()
    assert ledger.auto_release(db, 1).payment_status == "released"
    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(90)


# --- Litige ---------------------------------------------------------------------


def test_dispute_freezes_the_escrow(db):
    finished(db)
    mission = ledger.open_dispute(db, 1, CLIENT_ID, "  Travail non fait  ")

    assert mission.status == "disputed"
    assert mission.dispute_reason == "Travail non fait"
    assert mission.dispute_deadline - mission.dispute_opened_at == timedelta(hours=48)

    mission.status_changed_at = mission.status_changed_at - timedelta(days=10)
    db.commit()
    refused("mission_disputed", lambda: ledger.confirm_completion(db, 1, CLIENT_ID))
    refused("mission_disputed", lambda: ledger.auto_release(db, 1))
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(0)


def test_dispute_can_be_opened_from_any_unsettled_paid_state(db):
    fund(db, mission_id=1)
    assert ledger.open_dispute(db, 1, CLIENT_ID, "x").status == "disputed"
    fund(db, mission_id=2, quote_ref=6)
    ledger.start_mission(db, 2, PROVIDER_ID)
    assert ledger.open_dispute(db, 2, CLIENT_ID, "x").status == "disputed"
    finished(db, mission_id=3, quote_ref=7)
    assert ledger.open_dispute(db, 3, CLIENT_ID, "x").status == "disputed"


def test_dispute_is_refused_before_payment_after_settlement_or_for_another_client(db):
    crud.create_mission(db, CLIENT_ID, 9, "service_plomberie", "Gombe")
    refused("not_paid", lambda: ledger.open_dispute(db, 9, CLIENT_ID, "x"))

    finished(db)
    refused("not_mission_client", lambda: ledger.open_dispute(db, 1, 999, "x"))
    ledger.confirm_completion(db, 1, CLIENT_ID)
    refused("already_settled", lambda: ledger.open_dispute(db, 1, CLIENT_ID, "x"))


@pytest.mark.parametrize("reason", ["", "   ", "x" * 1001])
def test_dispute_needs_a_reason(db, reason):
    fund(db)
    refused("invalid_reason", lambda: ledger.open_dispute(db, 1, CLIENT_ID, reason))


def test_full_refund_returns_everything_to_the_client_fees_included(db):
    disputed(db)

    mission = ledger.resolve_dispute(db, 1, decision="refund", admin_telegram_id=1)

    assert (mission.status, mission.payment_status) == ("cancelled", "refunded")
    assert bal(db, ledger.CLIENT, CLIENT_ID) == money(100)
    assert bal(db, ledger.PLATFORM, None) == money(0)
    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(0)
    assert_books_balanced(db)


def test_admin_release_pays_the_provider_like_a_confirmation(db):
    disputed(db)

    mission = ledger.resolve_dispute(db, 1, decision="release", admin_telegram_id=1)

    assert (mission.status, mission.payment_status) == ("completed", "released")
    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(90)
    assert bal(db, ledger.PLATFORM, None) == money(10)


@pytest.mark.parametrize(
    "percentage,provider,client",
    [(50, "45.00", "45.00"), (0, "0.00", "90.00"), (100, "90.00", "0.00"), ("33.33", "30.00", "60.00"), (12.5, "11.25", "78.75")],
)
def test_split_shares_the_provider_net_and_the_platform_keeps_its_commission(db, percentage, provider, client):
    disputed(db)

    mission = ledger.resolve_dispute(db, 1, decision="split", provider_percentage=percentage, admin_telegram_id=1)

    assert (mission.status, mission.payment_status) == ("completed", "split")
    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(provider)
    assert bal(db, ledger.CLIENT, CLIENT_ID) == money(client)
    assert bal(db, ledger.PLATFORM, None) == money(10)
    assert bal(db, ledger.ESCROW, 1) == money(0)
    settlement = ledger.mission_money_state(db, 1)["settlement"]
    assert (settlement["provider_amount"], settlement["client_amount"]) == (provider, client)
    assert_books_balanced(db)


@pytest.mark.parametrize("percentage", [-1, 100.01, "abc", None, float("nan")])
def test_split_refuses_an_invalid_percentage(db, percentage):
    disputed(db)
    refused("invalid_percentage", lambda: ledger.resolve_dispute(db, 1, decision="split", provider_percentage=percentage, admin_telegram_id=1))


def test_a_dispute_is_settled_once(db):
    disputed(db)
    ledger.resolve_dispute(db, 1, decision="split", provider_percentage=50, admin_telegram_id=1)
    ledger.resolve_dispute(db, 1, decision="split", provider_percentage=50, admin_telegram_id=1)  # rejeu
    refused("already_settled", lambda: ledger.resolve_dispute(db, 1, decision="refund", admin_telegram_id=1))
    refused("already_settled", lambda: ledger.resolve_dispute(db, 1, decision="split", provider_percentage=60, admin_telegram_id=1))

    assert bal(db, ledger.PROVIDER, PROVIDER_ID) == money(45)
    assert bal(db, ledger.CLIENT, CLIENT_ID) == money(45)


def test_only_a_disputed_mission_can_be_resolved(db):
    fund(db)
    refused("not_disputed", lambda: ledger.resolve_dispute(db, 1, decision="refund", admin_telegram_id=1))
    refused("invalid_decision", lambda: ledger.resolve_dispute(db, 1, decision="cancel", admin_telegram_id=1))


def test_wallet_refund_can_pay_a_later_mission(db):
    disputed(db)
    ledger.resolve_dispute(db, 1, decision="refund", admin_telegram_id=1)

    fund(db, mission_id=2, method="wallet", quote_ref=8)

    assert bal(db, ledger.CLIENT, CLIENT_ID) == money(0)
    assert bal(db, ledger.ESCROW, 2) == money(100)
    assert_books_balanced(db)
