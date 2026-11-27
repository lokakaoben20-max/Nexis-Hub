# ruff: noqa: F811  (fixtures pytest importées de test_whatsapp_postgres)
"""Suivi WhatsApp (étape 7) sur un vrai Postgres : migration d2e3f4a5b6c7,
avis d'un client sans Telegram.

Même garde-fou que test_whatsapp_postgres.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.tests.test_whatsapp_missions_postgres import _create, _register
from backend.tests.test_whatsapp_postgres import URL, alembic, backend, engine  # noqa: F401

REVISION = "d2e3f4a5b6c7"
PREVIOUS = "c1d2e3f4a5b6"

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


def _whatsapp_mission(backend):
    _register(backend.app)
    status, body = _create(backend.app)
    assert status == 200, body
    return body["mission"]["mission_id"]


def _review(connection, mission_id, *, telegram_id=None, with_account=True):
    connection.execute(
        text(
            "INSERT INTO bot_reviews (mission_id, client_telegram_id, provider_telegram_id, client_account_id, rating,"
            " created_at) SELECT mission_id, :telegram_id, 7, CASE WHEN :with_account THEN client_account_id END, 5,"
            " now() FROM bot_missions WHERE mission_id = :mission_id"
        ),
        {"mission_id": mission_id, "telegram_id": telegram_id, "with_account": with_account},
    )


def test_a_review_always_names_its_author(backend, engine):
    mission_id = _whatsapp_mission(backend)
    with pytest.raises(IntegrityError, match="ck_bot_reviews_client_known"):
        with engine.begin() as connection:
            _review(connection, mission_id, with_account=False)
    with engine.begin() as connection:
        _review(connection, mission_id)
        assert connection.execute(text("SELECT client_telegram_id FROM bot_reviews")).scalar_one() is None


def test_downgrade_refuses_to_drop_a_whatsapp_review(backend, engine):
    mission_id = _whatsapp_mission(backend)
    with engine.begin() as connection:
        _review(connection, mission_id)
    backend.database.engine.dispose()

    with pytest.raises(RuntimeError, match="retour arrière impossible"):
        alembic("downgrade", PREVIOUS)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM bot_reviews")).scalar_one() == 1


def test_upgrade_downgrade_and_upgrade_again_without_whatsapp_reviews(engine):
    alembic("upgrade", REVISION)
    alembic("downgrade", PREVIOUS)
    with engine.connect() as connection:
        nullable = connection.execute(
            text(
                "SELECT is_nullable FROM information_schema.columns"
                " WHERE table_name = 'bot_reviews' AND column_name = 'client_telegram_id'"
            )
        ).scalar_one()
    assert nullable == "NO"
    alembic("upgrade", REVISION)
