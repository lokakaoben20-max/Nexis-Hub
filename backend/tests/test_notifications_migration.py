"""Migration b0c1d2e3f4a5 (table `notifications`) sur un vrai Postgres.

Les alertes « Nouvel appareil » pas encore parties deviennent des
notifications avec le même contenu ; l'ancienne boîte d'envoi des appareils
disparaît. Ne s'exécute que si `NEXIS_TEST_POSTGRES_URL` désigne une base
Postgres jetable dont le nom finit par `_test` (schéma `public` effacé).
"""

import os

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

from backend.tests.test_app_devices_migration import alembic

URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
REVISION = "b0c1d2e3f4a5"
PREVIOUS = "a9b0c1d2e3f4"
OLD_COLUMNS = {"alert_due_at", "alert_sent_at", "alert_attempts"}

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


def _device(connection, account_id, label, due, sent=None):
    return connection.execute(
        text(
            "INSERT INTO devices (account_id, platform, public_key, key_thumbprint, attestation, label, app_version,"
            " money_unlocked_at, created_at, alert_due_at, alert_sent_at, alert_attempts)"
            " VALUES (:a, 'android', 'cle', md5(random()::text) || md5(random()::text), 'unverified', :label, '1.0', now(),"
            " '2026-11-20 09:30:00', :due, :sent, 0) RETURNING id"
        ),
        {"a": account_id, "label": label, "due": due, "sent": sent},
    ).scalar_one()


def test_pending_device_alerts_move_to_the_notification_table_and_back(engine):
    alembic("upgrade", PREVIOUS)
    with engine.begin() as connection:
        telegram_account = connection.execute(
            text("INSERT INTO accounts (roles, language, created_at) VALUES ('[]', 'fr', now()) RETURNING id")
        ).scalar_one()
        app_only_account = connection.execute(
            text("INSERT INTO accounts (roles, language, created_at) VALUES ('[]', 'fr', now()) RETURNING id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at)"
                " VALUES (:a, 'telegram', '42', now(), now())"
            ),
            {"a": telegram_account},
        )
        waiting = _device(connection, telegram_account, "Pixel 8", "2026-11-20 09:30:00")
        unreachable = _device(connection, app_only_account, None, "2026-11-20 09:30:00")
        already_sent = _device(connection, telegram_account, "Ancien", None, "2026-11-19 08:00:00")

    alembic("upgrade", REVISION)

    assert not OLD_COLUMNS & {column["name"] for column in inspect(engine).get_columns("devices")}
    with engine.begin() as connection:
        rows = {
            row.event_key: row
            for row in connection.execute(
                text("SELECT event_key, recipient_account_id, channel, message_key, params, buttons, status, last_error FROM notifications")
            )
        }
    assert set(rows) == {f"new_device:{waiting}", f"new_device:{unreachable}"}
    moved = rows[f"new_device:{waiting}"]
    assert (moved.recipient_account_id, moved.channel, moved.status, moved.message_key) == (
        telegram_account, "telegram", "pending", "app_new_device_alert"
    )
    # Heure de Kinshasa, comme l'ancienne alerte.
    assert moved.params == {"device": "Pixel 8", "date": "20/11/2026", "time": "10:30"}
    assert moved.buttons == [[{"label": "button_app_not_me", "action": f"app_not_me_{waiting}"}]]
    lost = rows[f"new_device:{unreachable}"]
    assert (lost.channel, lost.status, lost.last_error) == (None, "failed", "no_channel")
    assert lost.params["device"] == {"$message": "app_device_unnamed"}

    for statement in (
        # Même événement, même destinataire : refusé.
        f"INSERT INTO notifications (event_key, recipient_account_id, channel, message_key, params, buttons, status,"
        f" attempts, uncertain_count, created_at) VALUES ('new_device:{waiting}', {telegram_account}, 'telegram',"
        " 'x', '{}', '[]', 'pending', 0, 0, now())",
        # « Envoyée » sans heure d'envoi : refusé.
        f"INSERT INTO notifications (event_key, recipient_account_id, channel, message_key, params, buttons, status,"
        f" attempts, uncertain_count, created_at) VALUES ('autre:1', {telegram_account}, 'telegram',"
        " 'x', '{}', '[]', 'sent', 1, 0, now())",
        f"INSERT INTO notifications (event_key, recipient_account_id, channel, message_key, params, buttons, status,"
        f" attempts, uncertain_count, created_at) VALUES ('autre:2', {telegram_account}, 'sms',"
        " 'x', '{}', '[]', 'pending', 0, 0, now())",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement))

    alembic("downgrade", PREVIOUS)

    assert "notifications" not in inspect(engine).get_table_names()
    with engine.begin() as connection:
        devices = {
            row.id: row
            for row in connection.execute(text("SELECT id, alert_due_at, alert_sent_at FROM devices"))
        }
    assert devices[waiting].alert_due_at is not None
    assert devices[unreachable].alert_due_at is None  # échec définitif : rien à renvoyer
    assert devices[already_sent].alert_due_at is None
