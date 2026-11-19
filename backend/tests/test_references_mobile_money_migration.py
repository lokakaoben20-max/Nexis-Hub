"""Migration e7f8a9b0c1d2 (notre référence unique, envois de versement
comptés) sur un vrai Postgres.

Comme test_echeance_liberation_migration.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import os
from datetime import datetime

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from backend.tests.test_app_devices_migration import alembic
from backend.tests.test_echeance_liberation_migration import _insert_mission

URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
REVISION = "e7f8a9b0c1d2"
PREVIOUS = "d5e6f7a8b9c0"
UPDATED_AT = datetime(2026, 11, 18, 14, 5)

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


@pytest.fixture
def engine(monkeypatch):
    url = make_url(URL)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("NEXIS_TEST_POSTGRES_URL doit viser une base Postgres jetable dont le nom finit par _test")
    monkeypatch.setenv("DATABASE_URL", URL)
    engine = create_engine(URL, future=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


def _insert_account(connection):
    return connection.execute(text("INSERT INTO accounts (created_at) VALUES (now()) RETURNING id")).scalar_one()


def _insert_intent(connection, mission_id, account_id, status):
    connection.execute(
        text(
            "INSERT INTO payment_intents (mission_id, account_id, gateway, operator, phone, amount, currency,"
            " funding_request, status, expires_at, created_at, updated_at)"
            " VALUES (:mission, :account, 'simulation', 'mpesa', '+243810000000', 100, 'USD', '{}', :status,"
            " now(), now(), now())"
        ),
        {"mission": mission_id, "account": account_id, "status": status},
    )


def _insert_payout(connection, account_id, status):
    return connection.execute(
        text(
            "INSERT INTO payouts (account_id, gateway, operator, phone, amount, fee, currency, status, created_at, updated_at)"
            " VALUES (:account, 'simulation', 'airtel', '+243810000000', 50, 1, 'USD', :status, now(), :updated)"
            " RETURNING id"
        ),
        {"account": account_id, "status": status, "updated": UPDATED_AT},
    ).scalar_one()


def test_existing_rows_get_their_own_reference_and_sent_payouts_count_one_send(engine):
    alembic("upgrade", PREVIOUS)
    with engine.begin() as connection:
        account = _insert_account(connection)
        mission = _insert_mission(connection, "in_progress")
        _insert_intent(connection, mission, account, "succeeded")
        _insert_intent(connection, mission, account, "failed")
        sent = _insert_payout(connection, account, "processing")
        waiting = _insert_payout(connection, account, "awaiting_approval")

    alembic("upgrade", REVISION)

    with engine.begin() as connection:
        intents = connection.execute(text("SELECT reference FROM payment_intents")).scalars().all()
        payouts = {row.id: row for row in connection.execute(text("SELECT id, reference, send_count, last_sent_at FROM payouts"))}
    assert len(set(intents)) == 2 and all(reference.startswith("NXI") and len(reference) == 35 for reference in intents)
    assert all(row.reference.startswith("NXO") for row in payouts.values())
    assert (payouts[sent].send_count, payouts[sent].last_sent_at) == (1, UPDATED_AT)
    assert (payouts[waiting].send_count, payouts[waiting].last_sent_at) == (0, None)

    with pytest.raises(IntegrityError):  # unique et obligatoire
        with engine.begin() as connection:
            connection.execute(text("UPDATE payment_intents SET reference = (SELECT min(reference) FROM payment_intents)"))
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("UPDATE payouts SET reference = NULL"))


def test_upgrade_downgrade_and_upgrade_again(engine):
    alembic("upgrade", "head")
    assert {"reference", "last_sent_at", "send_count"} <= {c["name"] for c in inspect(engine).get_columns("payouts")}

    alembic("downgrade", PREVIOUS)
    assert "reference" not in {c["name"] for c in inspect(engine).get_columns("payment_intents")}

    alembic("upgrade", REVISION)
    assert "reference" in {c["name"] for c in inspect(engine).get_columns("payment_intents")}
