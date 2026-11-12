"""Migration c8d9e0f1a2b3 (arrivée confirmée) sur un vrai Postgres.

Comme test_app_devices_migration.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from backend.tests.test_app_devices_migration import alembic
from backend.tests.test_mission_destination_migration import URL, _insert_mission, engine  # noqa: F401 (fixture)

REVISION = "c8d9e0f1a2b3"
PREVIOUS = "b7c8d9e0f1a2"

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


def _mission(connection) -> int:
    _insert_mission(connection, latitude=-4.3076, longitude=15.3125, landmark="Portail bleu")
    return connection.execute(text("SELECT max(mission_id) FROM bot_missions")).scalar_one()


def _insert_presence(connection, mission_id, **fields):
    columns = ["mission_id", *fields]
    connection.execute(
        text(f"INSERT INTO mission_presence ({', '.join(columns)}) VALUES ({', '.join(':' + column for column in columns)})"),
        {"mission_id": mission_id, **fields},
    )


def test_upgrade_downgrade_and_upgrade_again(engine):  # noqa: F811
    alembic("upgrade", "head")
    assert "mission_presence" in inspect(engine).get_table_names()

    alembic("downgrade", PREVIOUS)
    assert "mission_presence" not in inspect(engine).get_table_names()

    alembic("upgrade", REVISION)
    assert "mission_presence" in inspect(engine).get_table_names()


def test_valid_rows_are_accepted(engine):  # noqa: F811
    alembic("upgrade", "head")
    with engine.begin() as connection:
        _insert_presence(connection, _mission(connection))
        _insert_presence(connection, _mission(connection), confirmed_at="2026-11-08 12:00", confirmed_by="presence_code")
        _insert_presence(connection, _mission(connection), failed_code_attempts=5, code_locked_at="2026-11-08 12:00")
        attempts = connection.execute(text("SELECT failed_code_attempts FROM mission_presence ORDER BY mission_id")).scalars().all()
    assert attempts == [0, 0, 5], "0 essai par défaut"


@pytest.mark.parametrize(
    "fields",
    [
        {"confirmed_by": "client"},
        {"confirmed_at": "2026-11-08 12:00"},
        {"confirmed_at": "2026-11-08 12:00", "confirmed_by": "provider"},
        {"failed_code_attempts": 6, "code_locked_at": "2026-11-08 12:00"},
        {"failed_code_attempts": 5},
        {"failed_code_attempts": 2, "code_locked_at": "2026-11-08 12:00"},
        {"failed_code_attempts": -1},
    ],
    ids=["by_without_time", "time_without_by", "unknown_by", "too_many_attempts", "five_not_locked", "locked_early", "negative"],
)
def test_postgres_refuses_an_inconsistent_presence(engine, fields):  # noqa: F811
    alembic("upgrade", "head")
    with engine.begin() as connection:
        mission_id = _mission(connection)
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert_presence(connection, mission_id, **fields)


def test_a_presence_needs_an_existing_mission(engine):  # noqa: F811
    alembic("upgrade", "head")
    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert_presence(connection, 4242)


def test_client_and_code_at_the_same_instant_record_one_presence_on_postgres(engine, monkeypatch):  # noqa: F811
    """Verrou de la mission sur un vrai Postgres : le client appuie et le
    prestataire tape le code au même instant, une seule présence, un seul
    démarrage."""
    import importlib
    import threading

    from backend.tests.test_main import TEST_API_KEY, _authed_client
    from backend.tests.test_presence import CLIENT, PROVIDER, _paid_mission

    alembic("upgrade", "head")
    monkeypatch.setenv("BACKEND_API_KEY", TEST_API_KEY)
    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    from backend.app import ledger, presence
    from backend.app.models import MissionPresence

    with _authed_client(backend_main) as test_client:
        mission_id = _paid_mission(test_client, database_module)

    with database_module.SessionLocal() as db:
        client_account = ledger.account_id_for(db, ledger.TELEGRAM, CLIENT)
        provider_account = ledger.account_id_for(db, ledger.TELEGRAM, PROVIDER)
    code = presence.presence_code(mission_id)
    barrier = threading.Barrier(2)
    results, errors = [], []

    def run(operation):
        with database_module.SessionLocal() as db:
            barrier.wait()
            try:
                results.append(operation(db).changed)
            except Exception as error:  # noqa: BLE001
                errors.append(error)

    threads = [
        threading.Thread(target=run, args=(lambda db: presence.confirm_by_client(db, mission_id, client_account),)),
        threading.Thread(target=run, args=(lambda db: presence.confirm_by_code(db, mission_id, provider_account, code),)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert errors == []
    assert sorted(results) == [False, True], "un seul des deux a confirmé"
    with database_module.SessionLocal() as db:
        assert db.query(MissionPresence).filter_by(mission_id=mission_id).count() == 1
        assert db.get(ledger.BotMission, mission_id).status == "in_progress"
