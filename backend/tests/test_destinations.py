"""Numéros de retrait enregistrés (backend/app/destinations.py) et retraits
qui n'acceptent plus qu'eux (mobile_money.request_payout)."""

from datetime import timedelta

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app import destinations, ledger, mobile_money
from backend.app.models import Notification, PayoutDestination
from backend.tests.test_mobile_money import (  # noqa: F401 (fixtures)
    CLIENT_ID,
    PROVIDER_ID,
    acc,
    db,
    earn,
    gateway,
    refused,
)

FIRST, SECOND, THIRD, FOURTH, FIFTH = (f"+24397000000{n}" for n in range(1, 6))


def add(db, phone=FIRST, telegram_id=PROVIDER_ID, operator="airtel", from_bot=False):
    return destinations.add_destination(
        db, account_id=acc(db, telegram_id), operator=operator, phone=phone, first_only=from_bot
    )


def remove(db, destination_id, telegram_id=PROVIDER_ID):
    return destinations.remove_destination(db, account_id=acc(db, telegram_id), destination_id=destination_id)


def withdraw(db, destination_id, amount=20.0, telegram_id=PROVIDER_ID):
    return mobile_money.request_payout(
        db, account_id=acc(db, telegram_id), amount=amount, currency="USD", destination_id=destination_id
    )


def notifications(db, message_key):
    return db.query(Notification).filter(Notification.message_key == message_key).all()


def test_the_first_number_receives_money_right_away_without_any_name_check(db, gateway):
    earn(db, gateway)
    destination = add(db)
    assert (destination.status, destination.usable_after) == ("active", None)
    payout = withdraw(db, destination.id)
    assert (payout.destination_id, payout.phone, payout.operator) == (destination.id, FIRST, "airtel")
    assert payout.status in ("processing", "succeeded", "awaiting_approval")


def test_the_person_is_told_of_every_new_number_and_the_team_is_not_asked(db, gateway):
    destination = add(db)
    (told,) = notifications(db, "payout_destination_added")
    assert told.recipient_account_id == acc(db, PROVIDER_ID)
    assert told.params == {"operateur": "Airtel Money", "numero": FIRST}
    assert db.query(Notification).filter(Notification.recipient_account_id != destination.account_id).count() == 0


def test_a_number_added_after_the_first_waits_72_hours(db, gateway):
    earn(db, gateway)
    first = add(db)
    second = add(db, SECOND)
    assert second.usable_after == second.created_at + timedelta(hours=72)
    assert [n.params["date"] for n in notifications(db, "payout_destination_added_delayed")]

    refused("destination_too_new", lambda: withdraw(db, second.id))
    db.rollback()
    assert withdraw(db, first.id).destination_id == first.id, "l'ancien numéro sert toujours"

    second = db.get(PayoutDestination, second.id)
    second.usable_after = second.usable_after - timedelta(hours=72, seconds=1)
    db.commit()
    assert withdraw(db, second.id).destination_id == second.id


def test_removing_the_only_number_does_not_skip_the_delay(db, gateway):
    remove(db, add(db).id)
    replacement = add(db, SECOND)
    assert replacement.usable_after is not None


def test_a_bot_only_saves_the_very_first_number(db, gateway):
    first = add(db, from_bot=True)
    assert first.usable_after is None
    assert add(db, from_bot=True).id == first.id, "double envoi depuis le bot : le même numéro"
    refused("destination_change_in_app", lambda: add(db, SECOND, from_bot=True))
    db.rollback()
    remove(db, first.id)  # dans l'app
    refused("destination_change_in_app", lambda: add(db, SECOND, from_bot=True))
    db.rollback()
    assert add(db, SECOND).usable_after is not None, "dans l'app, avec le délai"


def test_the_same_number_sent_twice_is_one_destination_and_keeps_its_delay(db, gateway):
    add(db)
    second = add(db, SECOND)
    again = add(db, SECOND)
    assert again.id == second.id and again.usable_after == second.usable_after
    assert len(notifications(db, "payout_destination_added_delayed")) == 1


def test_a_database_never_holds_the_same_active_number_twice(db, gateway):
    first = add(db)
    with pytest.raises(IntegrityError):
        db.add(PayoutDestination(account_id=first.account_id, kind="mobile_money", operator="airtel", phone=FIRST, status="active"))
        db.flush()
    db.rollback()


def test_at_most_four_numbers(db, gateway):
    for phone in (FIRST, SECOND, THIRD, FOURTH):
        add(db, phone)
    refused("too_many_destinations", lambda: add(db, FIFTH))
    db.rollback()
    remove(db, add(db, FIRST).id)
    assert add(db, FIFTH).status == "active"


def test_someone_else_s_number_does_not_exist_for_you(db, gateway):
    earn(db, gateway)
    mine = add(db)
    refused("destination_not_found", lambda: withdraw(db, mine.id, telegram_id=CLIENT_ID))
    db.rollback()
    refused("destination_not_found", lambda: remove(db, mine.id, telegram_id=CLIENT_ID))
    db.rollback()
    assert db.get(PayoutDestination, mine.id).status == "active"


def test_a_removal_clicked_twice_is_recorded_once(db, gateway):
    destination = add(db)
    first = remove(db, destination.id).removed_at
    assert remove(db, destination.id).removed_at == first


def test_a_removed_number_keeps_the_payout_already_asked_but_takes_no_new_one(db, gateway):
    earn(db, gateway)
    gateway.payout = "pending"
    destination = add(db)
    payout = withdraw(db, destination.id)
    remove(db, destination.id)

    assert db.get(mobile_money.Payout, payout.id).phone == FIRST
    refused("destination_not_found", lambda: withdraw(db, destination.id))
    db.rollback()


@pytest.mark.parametrize(
    "phone,operator,code",
    [("0970000001", "airtel", "invalid_phone"), (FIRST, "africell", "invalid_operator")],
)
def test_number_and_operator_are_checked(db, gateway, phone, operator, code):
    refused(code, lambda: add(db, phone, operator=operator))
    db.rollback()
    assert db.query(PayoutDestination).count() == 0


def test_a_failed_payout_never_touches_the_destination(db, gateway):
    earn(db, gateway)
    gateway.payout = "failed"
    destination = add(db)
    payout = withdraw(db, destination.id)
    if payout.status == "awaiting_approval":
        payout = mobile_money.approve_payout(db, payout.id, 1)
    assert payout.status == "failed"
    assert db.get(PayoutDestination, destination.id).status == "active"
    assert ledger.balance(db, ledger.WALLET, acc(db, PROVIDER_ID), "USD") == 90, "le montant est revenu au wallet"
