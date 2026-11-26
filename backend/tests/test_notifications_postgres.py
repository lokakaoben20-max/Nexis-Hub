"""Boîte d'envoi sous accès simultanés, sur un vrai Postgres : les verrous
`FOR UPDATE SKIP LOCKED` de l'expéditeur n'existent pas sous SQLite.

Même garde-fou que test_litiges_postgres.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base d'administration Postgres dont le
nom finit par `_test`. Chaque test crée puis supprime sa propre base, quel
que soit `NEXIS_TEST_BACKEND_DB` : la CI les exécute dans ses deux passages.
"""

import importlib
import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from backend.tests.test_notifications import NOW, FakeTransport, _enqueue, _person

URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


@pytest.fixture
def env(monkeypatch):
    if not URL.rsplit("/", 1)[-1].split("?", 1)[0].endswith("_test"):
        pytest.fail("NEXIS_TEST_POSTGRES_URL doit viser une base jetable dont le nom finit par _test")
    name = f"nexis_t_{uuid.uuid4().hex[:16]}"
    admin = create_engine(URL, isolation_level="AUTOCOMMIT", future=True)
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    database = None
    try:
        monkeypatch.setenv("DATABASE_URL", URL.rsplit("/", 1)[0] + "/" + name)
        database = importlib.reload(importlib.import_module("backend.app.database"))
        models = importlib.reload(importlib.import_module("backend.app.models"))
        database.init_db()
        from backend.app import notifications

        monkeypatch.setattr(notifications, "_TRANSPORTS", {"telegram": FakeTransport()})
        yield database, models, notifications
    finally:
        if database is not None:
            database.engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def test_two_senders_never_take_the_same_notification(env):
    database, models, notifications = env
    account_id = _person(database)
    for number in range(4):
        _enqueue(database, notifications, account_id, f"test_event:{number}")

    with database.SessionLocal() as first:
        locked = (
            first.query(models.Notification)
            .order_by(models.Notification.id)
            .limit(2)
            .with_for_update()
            .all()
        )
        locked_ids = {row.id for row in locked}
        with database.SessionLocal() as second:
            claimed = notifications._claim(second, NOW, ["telegram"], 10)
        first.rollback()

    assert {notification_id for notification_id, _ in claimed}.isdisjoint(locked_ids)
    assert len(claimed) == 2
