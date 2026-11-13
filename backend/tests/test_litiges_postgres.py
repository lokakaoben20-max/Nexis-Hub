"""Décisions de litige sous accès simultanés, sur un vrai Postgres : les
verrous `FOR UPDATE` du registre n'existent pas sous SQLite.

Même garde-fou que test_whatsapp_postgres.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base d'administration Postgres dont le
nom finit par `_test`. Chaque test crée puis supprime sa propre base, quel
que soit `NEXIS_TEST_BACKEND_DB` : la CI les exécute dans ses deux passages.
"""

import os
import threading
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend.app import ledger
from backend.tests import profils_de_test
from backend.tests.test_ledger import (
    CLIENT_ID,
    PROVIDER_ID,
    LedgerEntry,
    MoneyOperation,
    acc,
    assert_books_balanced,
    bal,
    decide,
    disputed,
    first_decision,
    money,
)

URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


@pytest.fixture
def pg_url():
    if not URL.rsplit("/", 1)[-1].split("?", 1)[0].endswith("_test"):
        pytest.fail("NEXIS_TEST_POSTGRES_URL doit viser une base jetable dont le nom finit par _test")
    name = f"nexis_t_{uuid.uuid4().hex[:16]}"
    admin = create_engine(URL, isolation_level="AUTOCOMMIT", future=True)
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        yield URL.rsplit("/", 1)[0] + "/" + name
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def db(pg_url):
    engine = create_engine(pg_url, future=True)
    LedgerEntry.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)()
    profils_de_test.client(session, CLIENT_ID)
    profils_de_test.provider(session, PROVIDER_ID)
    yield session
    session.close()
    engine.dispose()


def _in_parallel(url, *calls):
    """Lance chaque appel dans sa propre session, au même instant, et renvoie
    pour chacun « ok » ou le code du refus."""
    engine = create_engine(url, future=True)
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


def test_two_simultaneous_executions_settle_once(db, pg_url):
    disputed(db)
    decide(db, "split", 50)
    row = first_decision(db)

    def execute(session):
        ledger.execute_dispute_decision(session, row.id, now=row.execute_after)

    assert _in_parallel(pg_url, execute, execute) == ["ok", "ok"]
    db.expire_all()
    assert db.query(MoneyOperation).filter(MoneyOperation.phase == ledger.SETTLEMENT).count() == 1
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(45)
    assert_books_balanced(db)


def test_a_contest_and_the_execution_at_the_same_time_only_one_wins(db, pg_url):
    disputed(db)
    decide(db, "release")
    row = first_decision(db)
    client_account = acc(db, CLIENT_ID)

    def execute(session):
        ledger.execute_dispute_decision(session, row.id, now=row.execute_after)

    def contest_now(session):
        ledger.contest_dispute_decision(session, 1, client_account, "Pas d'accord", now=row.execute_after - timedelta(seconds=1))

    executed, contested = _in_parallel(pg_url, execute, contest_now)

    db.expire_all()
    if ledger.mission_operation(db, 1, ledger.SETTLEMENT) is not None:
        assert (executed, contested) == ("ok", "decision_already_executed")
        assert first_decision(db).contested_at is None
    else:
        assert (executed, contested) == ("decision_contested", "ok")
        assert bal(db, ledger.ESCROW, 1) == money(100)


# --- Accord amiable ----------------------------------------------------------------


def _offer(db):
    return ledger.settlement_offers(db, 1)[-1]


def test_two_simultaneous_acceptances_settle_once(db, pg_url):
    disputed(db)
    ledger.propose_dispute_settlement(db, 1, acc(db, CLIENT_ID), kind="split", provider_percentage=50)
    offer_id, provider = _offer(db).id, acc(db, PROVIDER_ID)

    def accept(session):
        ledger.accept_dispute_settlement(session, 1, offer_id, provider)

    assert _in_parallel(pg_url, accept, accept) == ["ok", "ok"]
    db.expire_all()
    assert db.query(MoneyOperation).filter(MoneyOperation.phase == ledger.SETTLEMENT).count() == 1
    assert bal(db, ledger.WALLET, PROVIDER_ID) == money(45)
    assert_books_balanced(db)


def test_an_acceptance_and_a_decision_at_the_same_time_only_one_wins(db, pg_url):
    disputed(db)
    ledger.propose_dispute_settlement(db, 1, acc(db, CLIENT_ID), kind="release")
    offer_id, provider, admin = _offer(db).id, acc(db, PROVIDER_ID), acc(db, 900)
    db.commit()  # le compte de l'admin doit exister pour les autres sessions

    def accept(session):
        ledger.accept_dispute_settlement(session, 1, offer_id, provider)

    def decide_now(session):
        ledger.decide_dispute(session, 1, decision="refund", admin_account_id=admin, admin_telegram_id=900)

    results = _in_parallel(pg_url, accept, decide_now)
    db.expire_all()
    if results[0] == "ok":
        # L'accord gagne : la décision arrive sur un litige réglé.
        assert results[1] == "already_settled"
        assert bal(db, ledger.WALLET, PROVIDER_ID) == money(90)
        assert ledger.dispute_decisions(db, 1) == []
    else:
        # La décision gagne : la proposition est annulée, rien n'est versé.
        assert results == ["offer_closed", "ok"]
        assert _offer(db).status == "cancelled"
        assert db.query(MoneyOperation).filter(MoneyOperation.phase == ledger.SETTLEMENT).count() == 0
    assert_books_balanced(db)


def test_two_simultaneous_proposals_record_one(db, pg_url):
    disputed(db)
    client = acc(db, CLIENT_ID)

    def propose(kind):
        return lambda session: ledger.propose_dispute_settlement(session, 1, client, kind=kind)

    results = _in_parallel(pg_url, propose("release"), propose("refund"))
    db.expire_all()
    assert sorted(results) == ["offer_pending", "ok"]
    assert [row.status for row in ledger.settlement_offers(db, 1)] == ["pending"]
