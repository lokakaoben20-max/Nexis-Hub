"""Accord amiable sur un litige (« On s'est arrangés », plan des litiges 4.4).

Le client propose, le prestataire accepte ou refuse. Une proposition
acceptée règle tout de suite avec les montants figés à la proposition, ou
remet la mission en cours (`redo`). Une seule proposition à la fois, 48 h
pour répondre, plus rien une fois que Nexis Hub a décidé."""

from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app import ledger
from backend.app.models import DisputeSettlementOffer, LedgerEntry
from backend.tests import profils_de_test
from backend.tests.test_ledger import (
    CLIENT_ID,
    PROVIDER_ID,
    acc,
    assert_books_balanced,
    bal,
    decide,
    disputed,
    fund,
    money,
    operations,
    refused,
)


@pytest.fixture
def db(backend_db_url):
    engine = create_engine(backend_db_url, future=True)
    LedgerEntry.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    profils_de_test.client(session, CLIENT_ID)
    profils_de_test.provider(session, PROVIDER_ID)
    yield session
    session.close()
    engine.dispose()


def propose(db, kind="split", percentage=None, who=CLIENT_ID, mission_id=1, now=None):
    return ledger.propose_dispute_settlement(db, mission_id, acc(db, who), kind=kind, provider_percentage=percentage, now=now)


def offer(db, mission_id=1):
    return ledger.settlement_offers(db, mission_id)[-1]


def accept(db, offer_id=None, who=PROVIDER_ID, mission_id=1, now=None):
    offer_id = offer_id if offer_id is not None else offer(db, mission_id).id
    return ledger.accept_dispute_settlement(db, mission_id, offer_id, acc(db, who), now=now)


def decline(db, offer_id=None, who=PROVIDER_ID, mission_id=1, now=None):
    offer_id = offer_id if offer_id is not None else offer(db, mission_id).id
    return ledger.decline_dispute_settlement(db, mission_id, offer_id, acc(db, who), now=now)


def settlements(db, mission_id=1):
    return [operation for operation in operations(db, mission_id) if operation.phase == ledger.SETTLEMENT]


# --- Proposer ---------------------------------------------------------------------


def test_a_proposal_moves_no_money_and_freezes_its_amounts(db):
    disputed(db)

    mission = propose(db, "split", 50)

    assert mission.status == "disputed"
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert settlements(db) == []
    view = ledger.mission_money_state(db, 1)["dispute_offers"]
    assert len(view) == 1
    assert (view[0]["kind"], view[0]["state"], view[0]["percentage"]) == ("split", "pending", "50.00")
    assert (view[0]["provider_amount"], view[0]["client_amount"], view[0]["platform_amount"]) == ("45.00", "50.00", "5.00")
    row = offer(db)
    assert row.expires_at - row.proposed_at == timedelta(hours=48)


@pytest.mark.parametrize(
    "kind,percentage,provider,client,platform,status,payment_status",
    [
        ("release", None, "90.00", "0.00", "10.00", "completed", "released"),
        ("refund", None, "0.00", "100.00", "0.00", "cancelled", "refunded"),
        ("split", 50, "45.00", "50.00", "5.00", "completed", "split"),
        ("split", "33.33", "30.00", "66.67", "3.33", "completed", "split"),
    ],
)
def test_an_accepted_settlement_is_paid_at_once_without_a_contest_period(
    db, kind, percentage, provider, client, platform, status, payment_status
):
    disputed(db)
    propose(db, kind, percentage)

    mission = accept(db)

    assert (mission.status, mission.payment_status) == (status, payment_status)
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(provider)
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(client)
    assert bal(db, ledger.PLATFORM, None) == money(platform)
    assert bal(db, ledger.ESCROW, 1) == money(0)
    [operation] = settlements(db)
    assert operation.kind == "agreement"
    assert operation.actor_account_id == acc(db, PROVIDER_ID)
    state = ledger.mission_money_state(db, 1)
    assert (state["settlement"]["agreement"], state["settlement"]["offer_id"]) == (kind, offer(db).id)
    assert state["dispute_offers"][0]["state"] == "accepted"
    assert offer(db).settlement_operation_id == operation.id
    assert ledger.dispute_decisions(db, 1) == []
    assert_books_balanced(db)


def test_accepting_twice_settles_once(db):
    disputed(db)
    propose(db, "release")

    accept(db)
    mission = accept(db)

    assert mission.payment_status == "released"
    assert len(settlements(db)) == 1
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(90)
    refused("offer_closed", lambda: decline(db))


def test_redo_puts_the_mission_back_to_work_and_the_client_has_48_hours_again(db):
    disputed(db)
    propose(db, "redo")

    mission = accept(db)

    assert mission.status == "in_progress"
    assert (mission.release_after, mission.dispute_deadline) == (None, None)
    assert bal(db, ledger.ESCROW, 1) == money(100)
    assert settlements(db) == []
    assert offer(db).status == "accepted"
    assert offer(db).settlement_operation_id is None
    assert offer(db).provider_amount is None

    finished = ledger.finish_mission(db, 1, acc(db, PROVIDER_ID))
    assert finished.status == "awaiting_confirmation"
    assert finished.release_after == finished.status_changed_at + timedelta(hours=48)
    refused("invalid_state", lambda: ledger.auto_release(db, 1, now=finished.release_after - timedelta(minutes=1)))
    released = ledger.auto_release(db, 1, now=finished.release_after)
    assert released.payment_status == "released"
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(90)
    assert_books_balanced(db)


def test_after_a_redo_the_client_can_report_a_problem_again(db):
    disputed(db)
    propose(db, "redo")
    accept(db)

    mission = ledger.open_dispute(db, 1, acc(db, CLIENT_ID), "Toujours pas fini")

    assert mission.status == "disputed"
    assert mission.dispute_deadline is not None
    propose(db, "refund")
    assert accept(db).payment_status == "refunded"
    assert bal(db, ledger.WALLET, CLIENT_ID) == money(100)


# --- Qui fait quoi -------------------------------------------------------------------


def test_only_the_client_proposes_and_only_the_provider_answers(db):
    disputed(db)
    refused("not_mission_client", lambda: propose(db, "release", who=PROVIDER_ID))
    refused("not_mission_client", lambda: propose(db, "release", who=555))
    propose(db, "release")

    refused("offer_not_for_you", lambda: accept(db, who=CLIENT_ID))
    refused("offer_not_for_you", lambda: accept(db, who=555))
    refused("offer_not_for_you", lambda: decline(db, who=CLIENT_ID))
    assert offer(db).status == "pending"
    assert bal(db, ledger.ESCROW, 1) == money(100)


def test_an_offer_of_another_mission_cannot_settle_this_one(db):
    disputed(db, mission_id=1)
    disputed(db, mission_id=2, quote_ref=6)
    propose(db, "release", mission_id=2)

    refused("offer_not_found", lambda: accept(db, offer_id=offer(db, 2).id, mission_id=1))
    refused("offer_not_found", lambda: accept(db, offer_id=4242, mission_id=1))
    assert settlements(db, 1) == [] and settlements(db, 2) == []


# --- Une proposition à la fois, 48 h -----------------------------------------------------


def test_one_proposal_at_a_time_and_an_identical_one_is_a_replay(db):
    disputed(db)
    propose(db, "split", 50)

    propose(db, "split", "50.00")
    assert len(ledger.settlement_offers(db, 1)) == 1
    refused("offer_pending", lambda: propose(db, "split", 60))
    refused("offer_pending", lambda: propose(db, "refund"))

    decline(db)
    assert offer(db).status == "declined"
    assert ledger.mission_operation(db, 1, ledger.SETTLEMENT) is None
    propose(db, "split", 60)
    assert [row.status for row in ledger.settlement_offers(db, 1)] == ["declined", "pending"]


def test_declining_keeps_the_money_frozen_and_is_idempotent(db):
    disputed(db)
    propose(db, "release")

    mission = decline(db)
    decline(db)

    assert mission.status == "disputed"
    assert bal(db, ledger.ESCROW, 1) == money(100)
    refused("offer_closed", lambda: accept(db))
    assert settlements(db) == []


def test_an_offer_expires_after_48_hours(db):
    disputed(db)
    propose(db, "release")
    row = offer(db)

    refused("offer_expired", lambda: accept(db, now=row.expires_at))
    refused("offer_expired", lambda: decline(db, now=row.expires_at))
    assert ledger.settlement_offer_view(row, now=row.expires_at)["state"] == "expired"
    assert ledger.settlement_offer_view(row, now=row.expires_at - timedelta(seconds=1))["state"] == "pending"
    assert bal(db, ledger.ESCROW, 1) == money(100)

    # Une seconde avant l'échéance, la réponse passe encore.
    assert accept(db, now=row.expires_at - timedelta(seconds=1)).payment_status == "released"


def test_the_scheduler_marks_an_expired_offer_once_and_a_new_one_can_follow(db):
    disputed(db)
    propose(db, "release")
    row = offer(db)

    assert ledger.expire_dispute_settlement(db, row.id, now=row.expires_at - timedelta(seconds=1)) is False
    assert ledger.expire_dispute_settlement(db, row.id, now=row.expires_at) is True
    assert ledger.expire_dispute_settlement(db, row.id, now=row.expires_at) is False
    db.refresh(row)
    assert (row.status, row.closed_at) == ("expired", row.expires_at)

    propose(db, "refund", now=row.expires_at + timedelta(minutes=1))
    assert [r.status for r in ledger.settlement_offers(db, 1)] == ["expired", "pending"]


def test_a_new_proposal_replaces_an_expired_one_not_yet_marked(db):
    disputed(db)
    propose(db, "release")
    row = offer(db)

    propose(db, "refund", now=row.expires_at)

    assert [(r.kind, r.status) for r in ledger.settlement_offers(db, 1)] == [("release", "expired"), ("refund", "pending")]
    refused("offer_expired", lambda: accept(db, offer_id=row.id, now=row.expires_at))


# --- Décision de Nexis Hub -------------------------------------------------------------


def test_a_decision_cancels_the_pending_offer_and_ends_agreements(db):
    disputed(db)
    propose(db, "release")
    row = offer(db)

    decide(db, "refund")

    db.refresh(row)
    assert row.status == "cancelled"
    refused("offer_closed", lambda: accept(db, offer_id=row.id))
    refused("already_decided", lambda: propose(db, "split", 50))
    assert settlements(db) == []
    assert bal(db, ledger.ESCROW, 1) == money(100)


def test_no_agreement_on_a_mission_that_is_not_in_dispute_or_already_settled(db):
    fund(db)
    refused("not_disputed", lambda: propose(db, "release"))

    disputed(db, mission_id=2, quote_ref=6)
    propose(db, "refund", mission_id=2)
    accept(db, mission_id=2)
    refused("already_settled", lambda: propose(db, "release", mission_id=2))


@pytest.mark.parametrize("kind,percentage,code", [("pay_half", None, "invalid_offer"), ("split", None, "invalid_percentage"), ("split", 101, "invalid_percentage"), ("split", -1, "invalid_percentage"), ("split", "abc", "invalid_percentage")])
def test_invalid_proposals_are_refused(db, kind, percentage, code):
    disputed(db)
    refused(code, lambda: propose(db, kind, percentage))
    assert db.query(DisputeSettlementOffer).count() == 0


def test_the_amounts_paid_are_the_ones_shown_to_the_provider(db):
    """Le prestataire accepte ce qu'on lui a montré : les montants figés à la
    proposition sont ceux du règlement."""
    disputed(db)
    propose(db, "split", "12.5")
    row = offer(db)
    shown = (row.provider_amount, row.client_amount, row.platform_amount)

    accept(db)

    settlement = ledger.mission_money_state(db, 1)["settlement"]
    assert (money(settlement["provider_amount"]), money(settlement["client_amount"]), money(settlement["platform_amount"])) == shown
