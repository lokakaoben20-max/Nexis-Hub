"""Migration 0a1b2c3d4e5f (application mobile) sur un vrai Postgres.

La chaîne de migrations du dépôt ne tourne que sur Postgres (des étapes plus
anciennes modifient des contraintes, ce que SQLite ne sait pas faire). Ce test
ne s'exécute donc que si `NEXIS_TEST_POSTGRES_URL` désigne une base Postgres
jetable, dont le nom finit par `_test` : il efface entièrement son schéma
`public`. Garde-fou : tout autre nom de base est refusé, pour ne jamais
toucher une vraie base par erreur.

Exemple : NEXIS_TEST_POSTGRES_URL=postgresql+psycopg://postgres@localhost:5432/nexis_test
"""

import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parents[2]
URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
REVISION = "0a1b2c3d4e5f"
PREVIOUS = "c3d4e5f6a7b8"
APP_TABLES = {"devices", "app_sessions", "login_challenges", "request_nonces", "auth_events"}

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


def alembic(command_name, revision):
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    getattr(command, command_name)(config, revision)


def tables(engine):
    return set(inspect(engine).get_table_names())


def test_upgrade_downgrade_and_upgrade_again(engine):
    alembic("upgrade", "head")
    assert APP_TABLES <= tables(engine)

    alembic("downgrade", PREVIOUS)
    assert not (APP_TABLES & tables(engine))
    assert {"accounts", "channel_identities", "ledger_entries", "money_operations"} <= tables(engine)

    alembic("upgrade", REVISION)
    assert APP_TABLES <= tables(engine)


def _insert_device(connection, account_id=None, **overrides):
    now = datetime(2026, 11, 7, 8, 0, 0)
    values = dict(
        account_id=account_id,
        platform="android",
        public_key="cle",
        key_thumbprint="a" * 64,
        attestation="verified",
        app_version="1.0.0",
        money_unlocked_at=now + timedelta(hours=72),
        created_at=now,
        revoked_at=None,
        revoked_reason=None,
    )
    values.update(overrides)
    connection.execute(
        text(
            "INSERT INTO devices (account_id, platform, public_key, key_thumbprint, attestation, app_version,"
            " money_unlocked_at, created_at, revoked_at, revoked_reason)"
            " VALUES (:account_id, :platform, :public_key, :key_thumbprint, :attestation, :app_version,"
            " :money_unlocked_at, :created_at, :revoked_at, :revoked_reason)"
        ),
        values,
    )


@pytest.mark.parametrize(
    "overrides",
    [
        {"account_id": 999_999},
        {"platform": "windows"},
        {"attestation": "maybe"},
        {"revoked_at": datetime(2026, 11, 8)},
        {"money_unlocked_at": datetime(2026, 11, 6)},
    ],
    ids=["unknown_account", "platform", "attestation", "revoked_without_reason", "unlock_before_creation"],
)
def test_postgres_refuses_impossible_devices(engine, overrides):
    alembic("upgrade", "head")
    with engine.begin() as connection:
        account_id = connection.execute(text("INSERT INTO accounts (roles, language, created_at) VALUES ('[]', 'fr', now()) RETURNING id")).scalar_one()
        _insert_device(connection, account_id)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert_device(connection, **{"account_id": account_id, "key_thumbprint": "b" * 64, **overrides})


def test_postgres_refuses_a_second_device_with_the_same_key(engine):
    alembic("upgrade", "head")
    with engine.begin() as connection:
        account_id = connection.execute(text("INSERT INTO accounts (roles, language, created_at) VALUES ('[]', 'fr', now()) RETURNING id")).scalar_one()
        _insert_device(connection, account_id)

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            _insert_device(connection, account_id)


def test_postgres_limits_code_attempts(engine):
    alembic("upgrade", "head")
    insert = text(
        "INSERT INTO login_challenges (public_id, phone_e164, purpose, delivery, device_key_thumbprint, attempts,"
        " created_at, expires_at) VALUES (:public_id, '+243810000001', 'signup', 'telegram', :thumb, :attempts,"
        " now(), now() + interval '10 minutes')"
    )
    with engine.begin() as connection:
        connection.execute(insert, {"public_id": "p" * 32, "thumb": "a" * 64, "attempts": 5})

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(insert, {"public_id": "q" * 32, "thumb": "a" * 64, "attempts": 6})
