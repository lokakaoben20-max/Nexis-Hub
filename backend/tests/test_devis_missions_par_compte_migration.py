"""Migration a4b5c6d7e8f9 (devis, missions et avis rattachés aux comptes) sur
un vrai Postgres.

Comme test_echeance_liberation_migration.py : ne s'exécute que si
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
REVISION = "a4b5c6d7e8f9"
PREVIOUS = "e3f4a5b6c7d8"
CLIENT_TELEGRAM = 42
PROVIDER_TELEGRAM = 7

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


def nullable(engine, table):
    return {column["name"]: column["nullable"] for column in inspect(engine).get_columns(table)}


def _account(connection, telegram_id=None):
    account_id = connection.execute(
        text("INSERT INTO accounts (roles, language, created_at) VALUES ('[]', 'fr', now()) RETURNING id")
    ).scalar_one()
    if telegram_id is not None:
        connection.execute(
            text(
                "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at)"
                " VALUES (:account_id, 'telegram', :external_id, now(), now())"
            ),
            {"account_id": account_id, "external_id": str(telegram_id)},
        )
    return account_id


def _legacy_mission(connection, provider_telegram=PROVIDER_TELEGRAM):
    """Mission d'avant les comptes : client et prestataire par Telegram seul."""
    return connection.execute(
        text(
            "INSERT INTO bot_missions (telegram_id, provider_telegram_id, service, commune, currency, description,"
            " urgent, status, commission_amount, tola_fee, aggregator_fee, total_client, net_provider, created_at,"
            " status_changed_at, reminder_sent_10min, reminder_sent_20min)"
            " VALUES (:client, :provider, 'service_plomberie', 'Gombe', 'USD', '', false, 'completed', 0, 0, 0, 0, 0,"
            " now(), now(), false, false) RETURNING mission_id"
        ),
        {"client": CLIENT_TELEGRAM, "provider": provider_telegram},
    ).scalar_one()


def _legacy_quote(connection, mission_id, provider_telegram=PROVIDER_TELEGRAM):
    return connection.execute(
        text(
            "INSERT INTO bot_quotes (mission_id, provider_telegram_id, amount, currency, delay_hours, message, status,"
            " created_at) VALUES (:mission_id, :provider, 50, 'USD', 2, '', 'accepted', now()) RETURNING id"
        ),
        {"mission_id": mission_id, "provider": provider_telegram},
    ).scalar_one()


def _legacy_review(connection, mission_id):
    return connection.execute(
        text(
            "INSERT INTO bot_reviews (mission_id, client_telegram_id, provider_telegram_id, rating, created_at)"
            " VALUES (:mission_id, :client, :provider, 5, now()) RETURNING id"
        ),
        {"mission_id": mission_id, "client": CLIENT_TELEGRAM, "provider": PROVIDER_TELEGRAM},
    ).scalar_one()


def test_rows_from_before_accounts_are_linked_through_their_telegram_identity(engine):
    alembic("upgrade", PREVIOUS)
    with engine.begin() as connection:
        client = _account(connection, CLIENT_TELEGRAM)
        provider = _account(connection, PROVIDER_TELEGRAM)
        mission_id = _legacy_mission(connection)
        quote_id = _legacy_quote(connection, mission_id)
        review_id = _legacy_review(connection, mission_id)

    alembic("upgrade", REVISION)

    with engine.begin() as connection:
        assert connection.execute(
            text("SELECT client_account_id, provider_account_id FROM bot_missions WHERE mission_id = :id"), {"id": mission_id}
        ).one() == (client, provider)
        assert connection.execute(
            text("SELECT provider_account_id FROM bot_quotes WHERE id = :id"), {"id": quote_id}
        ).scalar_one() == provider
        assert connection.execute(
            text("SELECT client_account_id, provider_account_id FROM bot_reviews WHERE id = :id"), {"id": review_id}
        ).one() == (client, provider)

    assert nullable(engine, "bot_quotes")["provider_account_id"] is False
    assert nullable(engine, "bot_quotes")["provider_telegram_id"] is True
    assert nullable(engine, "bot_reviews")["client_account_id"] is False
    assert nullable(engine, "bot_reviews")["provider_account_id"] is False
    assert nullable(engine, "bot_reviews")["provider_telegram_id"] is True
    assert nullable(engine, "bot_missions")["client_account_id"] is False


def test_a_row_that_cannot_be_linked_stops_the_migration_and_is_named(engine):
    """Aucun compte n'est fabriqué : la ligne est nommée, rien ne change."""
    alembic("upgrade", PREVIOUS)
    with engine.begin() as connection:
        _account(connection, CLIENT_TELEGRAM)
        _account(connection, PROVIDER_TELEGRAM)
        mission_id = _legacy_mission(connection)
        orphan = _legacy_quote(connection, mission_id, provider_telegram=999)
        accounts_before = connection.execute(text("SELECT count(*) FROM accounts")).scalar_one()

    with pytest.raises(RuntimeError, match=rf"bot_quotes\.provider_account_id manquant, id : {orphan}"):
        alembic("upgrade", REVISION)

    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM accounts")).scalar_one() == accounts_before
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == PREVIOUS
        assert connection.execute(
            text("SELECT provider_account_id FROM bot_quotes WHERE id = :id"), {"id": orphan}
        ).scalar_one() is None


def test_a_provider_named_by_telegram_always_has_its_account(engine):
    alembic("upgrade", "head")
    with engine.begin() as connection:
        _account(connection, CLIENT_TELEGRAM)
    with pytest.raises(IntegrityError, match="ck_bot_missions_provider_account"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO bot_missions (telegram_id, client_account_id, provider_telegram_id, service, commune,"
                    " currency, description, urgent, status, commission_amount, tola_fee, aggregator_fee, total_client,"
                    " net_provider, created_at, status_changed_at, reminder_sent_10min, reminder_sent_20min)"
                    " SELECT 42, id, 7, 'service_plomberie', 'Gombe', 'USD', '', false, 'confirmed', 0, 0, 0, 0, 0,"
                    " now(), now(), false, false FROM accounts LIMIT 1"
                )
            )


def test_downgrade_refuses_a_quote_from_a_provider_without_telegram(engine):
    alembic("upgrade", "head")
    with engine.begin() as connection:
        client = _account(connection, CLIENT_TELEGRAM)
        business = _account(connection)  # pas de Telegram
        mission_id = connection.execute(
            text(
                "INSERT INTO bot_missions (client_account_id, service, commune, currency, description, urgent, status,"
                " commission_amount, tola_fee, aggregator_fee, total_client, net_provider, created_at,"
                " status_changed_at, reminder_sent_10min, reminder_sent_20min)"
                " VALUES (:client, 'service_plomberie', 'Gombe', 'USD', '', false, 'quoted', 0, 0, 0, 0, 0, now(),"
                " now(), false, false) RETURNING mission_id"
            ),
            {"client": client},
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO bot_quotes (mission_id, provider_account_id, amount, currency, delay_hours, message, status,"
                " created_at) VALUES (:mission_id, :business, 50, 'USD', 2, '', 'pending', now())"
            ),
            {"mission_id": mission_id, "business": business},
        )

    with pytest.raises(RuntimeError, match="retour arrière impossible"):
        alembic("downgrade", PREVIOUS)
    with engine.begin() as connection:
        assert connection.execute(text("SELECT count(*) FROM bot_quotes")).scalar_one() == 1


def test_upgrade_downgrade_and_upgrade_again(engine):
    alembic("upgrade", "head")
    alembic("downgrade", PREVIOUS)
    assert nullable(engine, "bot_quotes")["provider_telegram_id"] is False
    assert nullable(engine, "bot_quotes")["provider_account_id"] is True
    assert nullable(engine, "bot_missions")["client_account_id"] is True
    alembic("upgrade", "head")
    assert nullable(engine, "bot_quotes")["provider_account_id"] is False
