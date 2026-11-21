"""Migration a9b0c1d2e3f4 (conditions d'utilisation) sur un vrai Postgres.

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
REVISION = "a9b0c1d2e3f4"
PREVIOUS = "f8a9b0c1d2e3"
TABLES = {"legal_document_versions", "legal_acceptances"}

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


def test_the_tables_come_and_go_with_the_migration_and_keep_their_rules(engine):
    alembic("upgrade", PREVIOUS)
    assert not TABLES & set(inspect(engine).get_table_names())
    alembic("upgrade", REVISION)
    assert TABLES <= set(inspect(engine).get_table_names())

    with engine.begin() as connection:
        account_id = connection.execute(text("INSERT INTO accounts (roles, language, created_at) VALUES ('[]', 'fr', now()) RETURNING id")).scalar_one()
        version_id = connection.execute(
            text(
                "INSERT INTO legal_document_versions (document_key, version, language, text, text_sha256, effective_at, published_at)"
                " VALUES ('cgu', 'v1', 'fr', 'Texte', repeat('0', 64), now(), now()) RETURNING id"
            )
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO legal_acceptances (account_id, version_id, role, surface, language, accepted_at)"
                " VALUES (:a, :v, 'client', 'whatsapp', 'ln', now())"
            ),
            {"a": account_id, "v": version_id},
        )
    for statement in (
        # Deuxième ligne pour la même version : refusée.
        "INSERT INTO legal_acceptances (account_id, version_id, role, surface, language, accepted_at)"
        " VALUES (:a, :v, 'provider', 'app', 'fr', now())",
        "INSERT INTO legal_acceptances (account_id, version_id, role, surface, language, accepted_at)"
        " VALUES (:a, :v, 'admin', 'app', 'fr', now())",
        "INSERT INTO legal_document_versions (document_key, version, language, text, text_sha256, effective_at, published_at)"
        " VALUES ('cgu', 'v1', 'fr', 'Autre', repeat('1', 64), now(), now())",
        "INSERT INTO legal_document_versions (document_key, version, language, text, text_sha256, effective_at, published_at)"
        " VALUES ('charte', 'v1', 'fr', 'Texte', repeat('0', 64), now(), now())",
    ):
        with pytest.raises(IntegrityError), engine.begin() as connection:
            connection.execute(text(statement), {"a": account_id, "v": version_id})

    alembic("downgrade", PREVIOUS)
    assert not TABLES & set(inspect(engine).get_table_names())
