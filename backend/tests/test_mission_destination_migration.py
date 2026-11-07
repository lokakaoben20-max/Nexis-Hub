"""Migration b7c8d9e0f1a2 (lieu exact de la mission) sur un vrai Postgres.

Comme test_app_devices_migration.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from backend.tests.test_app_devices_migration import alembic

URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
REVISION = "b7c8d9e0f1a2"
PREVIOUS = "0a1b2c3d4e5f"
COLUMNS = {"destination_latitude", "destination_longitude", "destination_landmark"}

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


def _insert_mission(connection, **destination):
    connection.execute(
        text(
            "INSERT INTO bot_missions (telegram_id, service, commune, currency, description, urgent,"
            " commission_amount, tola_fee, aggregator_fee, total_client, net_provider, created_at,"
            " status_changed_at, reminder_sent_10min, reminder_sent_20min,"
            " destination_latitude, destination_longitude, destination_landmark)"
            " VALUES (42, 'service_plomberie', 'Gombe', 'USD', '', false, 0, 0, 0, 0, 0, now(), now(), false, false,"
            " :latitude, :longitude, :landmark)"
        ),
        {"latitude": None, "longitude": None, "landmark": None, **destination},
    )


def test_upgrade_downgrade_and_upgrade_again(engine):
    alembic("upgrade", "head")
    assert COLUMNS <= mission_columns(engine)

    alembic("downgrade", PREVIOUS)
    assert not (COLUMNS & mission_columns(engine))

    alembic("upgrade", REVISION)
    assert COLUMNS <= mission_columns(engine)


def test_an_old_mission_without_place_and_a_complete_place_are_accepted(engine):
    alembic("upgrade", "head")
    with engine.begin() as connection:
        _insert_mission(connection)
        _insert_mission(connection, latitude=-4.3076, longitude=15.3125, landmark="Portail bleu")


@pytest.mark.parametrize(
    "destination",
    [
        {"latitude": -4.3076, "longitude": 15.3125},
        {"latitude": -4.3076, "landmark": "Portail bleu"},
        {"landmark": "Portail bleu"},
    ],
    ids=["no_landmark", "no_longitude", "landmark_only"],
)
def test_postgres_refuses_a_partial_place(engine, destination):
    alembic("upgrade", "head")
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert_mission(connection, **destination)
