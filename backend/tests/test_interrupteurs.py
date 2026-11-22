"""Interrupteurs d'arrêt Mobile Money (backend/app/interrupteurs.py) : couper
les encaissements ou les versements sans redéployer, sans jamais perdre ni
doubler l'argent déjà en route."""

from datetime import timedelta

import pytest
from sqlalchemy.orm import sessionmaker

from backend.app import interrupteurs, ledger, mobile_money, reconciliation
from backend.app.models import MoneySwitchEvent
from backend.tests.test_mobile_money import (  # noqa: F401 (fixtures)
    ADMIN_ID,
    CLIENT_ID,
    PROVIDER_ID,
    Payout,
    PaymentIntent,
    acc,
    assert_books_balanced,
    balance,
    db,
    earn,
    gateway,
    money,
    older,
    pay,
    refused,
    wallet,
    withdraw,
)

COLLECTIONS, PAYOUTS = interrupteurs.COLLECTIONS, interrupteurs.PAYOUTS


def cut(db, name, reason="fraude suspectée", by=ADMIN_ID):
    return interrupteurs.switch(db, name, open=False, reason=reason, source="bot", by_telegram_id=by)


def reopen(db, name, reason="vérifié avec l'agrégateur", by=ADMIN_ID):
    return interrupteurs.switch(db, name, open=True, reason=reason, source="bot", by_telegram_id=by)


def test_both_flows_are_open_until_an_admin_cuts_one(db):
    assert interrupteurs.is_open(db, COLLECTIONS) and interrupteurs.is_open(db, PAYOUTS)
    assert [item["is_open"] for item in interrupteurs.state(db)] == [True, True]


def test_cut_collections_send_no_new_payment_request(db, gateway):
    cut(db, COLLECTIONS)

    refused("payments_paused", lambda: pay(db))
    assert gateway.known == {}  # rien n'est parti vers l'agrégateur
    assert db.query(PaymentIntent).count() == 0
    assert interrupteurs.is_open(db, PAYOUTS)  # l'autre flux ne bouge pas


def test_a_payment_already_sent_is_still_confirmed_while_collections_are_cut(db, gateway):
    gateway.collection = "pending"
    intent = pay(db)
    cut(db, COLLECTIONS)

    assert pay(db).id == intent.id  # second clic : la même intention, rien de nouveau
    gateway.collection = "succeeded"  # le client valide sur son téléphone
    assert mobile_money.refresh_intent(db, intent.id).status == "succeeded"
    assert balance(db, ledger.ESCROW, 1) == money(100)
    assert_books_balanced(db)


def test_cut_payouts_refuse_new_withdrawals_without_holding_anything(db, gateway):
    earn(db, gateway)
    cut(db, PAYOUTS)

    refused("payouts_paused", lambda: withdraw(db))
    assert wallet(db, PROVIDER_ID) == money(90)
    assert db.query(Payout).count() == 0


def test_cut_payouts_cannot_be_approved_but_can_be_rejected(db, gateway):
    earn(db, gateway)
    first, second = withdraw(db, 30), withdraw(db, 20)
    cut(db, PAYOUTS)

    refused("payouts_paused", lambda: mobile_money.approve_payout(db, first.id, ADMIN_ID))
    assert db.get(Payout, first.id).status == "awaiting_approval"
    assert gateway.payout_requests == 0

    assert mobile_money.reject_payout(db, second.id, ADMIN_ID, "doute").status == "rejected"
    assert wallet(db, PROVIDER_ID) == money(60)  # 90 - 30 encore bloqués
    assert_books_balanced(db)


def test_an_approved_payout_caught_by_the_cut_waits_then_leaves_once_reopened(db, gateway):
    earn(db, gateway)
    payout = withdraw(db)
    # L'admin a validé juste avant la coupure, l'envoi arrive juste après.
    payout.status = "processing"
    db.commit()
    cut(db, PAYOUTS)

    assert mobile_money._send_payout(db, payout.id).send_count == 0
    older(payout, "updated_at", timedelta(hours=1))
    db.commit()
    assert mobile_money.refresh_payout(db, payout.id).status == "processing"  # inconnu, mais coupé : rien ne part
    assert gateway.payout_requests == 0
    assert balance(db, ledger.PAYOUT_PENDING, payout.id) == money(50)  # ni versé ni rendu

    reopen(db, PAYOUTS)
    payout = mobile_money.refresh_payout(db, payout.id)
    assert (payout.status, payout.send_count) == ("succeeded", 1)
    assert gateway.payout_requests == 1
    assert_books_balanced(db)


def test_a_payout_already_sent_is_still_read_but_never_resent_while_cut(db, gateway):
    earn(db, gateway)
    gateway.drop_requests = True
    payout = mobile_money.approve_payout(db, withdraw(db).id, ADMIN_ID)
    gateway.drop_requests = False
    cut(db, PAYOUTS)

    older(payout, "last_sent_at", mobile_money.PAYOUT_RESEND_AFTER + timedelta(seconds=1))
    db.commit()
    assert mobile_money.refresh_payout(db, payout.id).send_count == 1
    assert gateway.payout_requests == 1

    reopen(db, PAYOUTS)
    assert mobile_money.refresh_payout(db, payout.id).status == "succeeded"
    assert gateway.duplicates_refused == 0


def test_every_change_needs_a_reason_and_is_kept_in_the_journal(db):
    with pytest.raises(ledger.MoneyError) as error:
        interrupteurs.switch(db, PAYOUTS, open=False, reason="  ", source="bot", by_telegram_id=ADMIN_ID)
    assert error.value.code == "reason_required"
    with pytest.raises(ledger.MoneyError) as error:
        cut(db, "wallets")
    assert (error.value.code, error.value.http_status) == ("unknown_switch", 404)

    assert cut(db, PAYOUTS)[1] is True
    assert cut(db, PAYOUTS, reason="deuxième clic")[1] is False  # déjà coupés : rien n'est écrit
    reopen(db, PAYOUTS, by=None)

    events = db.query(MoneySwitchEvent).order_by(MoneySwitchEvent.id).all()
    assert [(event.name, event.is_open, event.by_telegram_id, event.reason) for event in events] == [
        (PAYOUTS, False, ADMIN_ID, "fraude suspectée"),
        (PAYOUTS, True, None, "vérifié avec l'agrégateur"),
    ]
    assert interrupteurs.is_open(db, PAYOUTS)


def test_the_daily_report_reminds_the_admins_of_a_cut_flow(db, gateway):
    cut(db, COLLECTIONS, reason="agrégateur en panne")
    report = reconciliation.reconcile(db, ledger._utcnow())

    assert report.ok  # pas un écart d'argent
    text = reconciliation.format_admin_report(report)
    assert "Encaissements coupés" in text and "agrégateur en panne" in text
    assert "Versements" not in text


def test_the_server_command_cuts_and_reopens_without_the_bot(db, monkeypatch, capsys):
    import backend.app.database as database

    monkeypatch.setattr(database, "SessionLocal", sessionmaker(bind=db.get_bind(), expire_on_commit=False))

    db.commit()  # la session du test ne garde aucune transaction ouverte
    assert interrupteurs.main(["couper", "versements", "--raison", "bot en panne"]) == 0
    assert not interrupteurs.is_open(db, PAYOUTS)
    db.commit()
    assert interrupteurs.main(["etat"]) == 0
    assert "Versements : COUPÉS" in capsys.readouterr().out
    assert interrupteurs.main(["rouvrir", "versements", "--raison", ""]) == 1  # raison obligatoire
    assert interrupteurs.main(["rouvrir", "versements", "--raison", "réparé"]) == 0

    db.expire_all()
    assert interrupteurs.is_open(db, PAYOUTS)
    events = db.query(MoneySwitchEvent).order_by(MoneySwitchEvent.id).all()
    assert [(event.source, event.by_telegram_id) for event in events] == [("cli", None), ("cli", None)]
    assert acc(db, CLIENT_ID)  # le compte de test est intact
