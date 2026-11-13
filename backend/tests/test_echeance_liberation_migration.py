"""Migration e0f1a2b3c4d5 (échéance de libération, litiges en retard) sur un
vrai Postgres.

Comme test_mission_destination_migration.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import os
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

from backend.tests.test_app_devices_migration import alembic

URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
REVISION = "e0f1a2b3c4d5"
PREVIOUS = "d9e0f1a2b3c4"
COLUMNS = {"release_after", "dispute_overdue_alerted_at"}
ENDED_AT = datetime(2026, 11, 10, 9, 30)

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


def mission_columns(engine):
    return {column["name"] for column in inspect(engine).get_columns("bot_missions")}


def _insert_mission(connection, status):
    return connection.execute(
        text(
            "INSERT INTO bot_missions (telegram_id, service, commune, currency, description, urgent, status,"
            " commission_amount, tola_fee, aggregator_fee, total_client, net_provider, created_at,"
            " status_changed_at, reminder_sent_10min, reminder_sent_20min)"
            " VALUES (42, 'service_plomberie', 'Gombe', 'USD', '', false, :status, 0, 0, 0, 0, 0, now(),"
            " :ended_at, false, false) RETURNING mission_id"
        ),
        {"status": status, "ended_at": ENDED_AT},
    ).scalar_one()


def test_missions_already_waiting_keep_the_24_hour_rule(engine):
    alembic("upgrade", PREVIOUS)
    with engine.begin() as connection:
        waiting = _insert_mission(connection, "awaiting_confirmation")
        in_progress = _insert_mission(connection, "in_progress")
        disputed = _insert_mission(connection, "disputed")

    alembic("upgrade", REVISION)

    with engine.begin() as connection:
        deadlines = dict(connection.execute(text("SELECT mission_id, release_after FROM bot_missions")).all())
    assert deadlines[waiting] == ENDED_AT + timedelta(hours=24)
    assert deadlines[in_progress] is None
    assert deadlines[disputed] is None


def test_upgrade_downgrade_and_upgrade_again(engine):
    alembic("upgrade", "head")
    assert COLUMNS <= mission_columns(engine)

    alembic("downgrade", PREVIOUS)
    assert not (COLUMNS & mission_columns(engine))

    alembic("upgrade", REVISION)
    assert COLUMNS <= mission_columns(engine)
