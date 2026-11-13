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
from backend.tests.test_ledger import (
    CLIENT_ID,
    PROVIDER_ID,
    BotProvider,
    BotUser,
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
    session.add(BotUser(telegram_id=CLIENT_ID, first_name="Client"))
    session.add(BotProvider(telegram_id=PROVIDER_ID, full_name="Prestataire"))
    session.commit()
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
