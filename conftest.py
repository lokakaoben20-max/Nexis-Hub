"""Réglages communs à tous les tests (tests/ et backend/tests/).

Les bases SQLite ouvertes par SQLAlchemy dans les tests (backend jetable) :

- sans fsync : sous Windows, chaque commit sur disque coûtait ~0,1 s ; on
  coupe la durabilité de ces bases jetables, pas la logique ;
- avec de vrais SAVEPOINT : le pilote sqlite3 gère lui-même ses
  transactions et casse les SAVEPOINT (un RELEASE validait tout). Le registre
  d'argent s'appuie dessus (`begin_nested`) : on applique la correction
  documentée par SQLAlchemy pour que SQLite se comporte comme Postgres.

Enregistré une seule fois ici : deux écouteurs « begin » émettraient BEGIN
deux fois. Les connexions sqlite3 directes de db.py ne sont pas concernées.
"""

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _sqlite_for_tests(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.isolation_level = None
        dbapi_connection.execute("PRAGMA synchronous = OFF")
        dbapi_connection.execute("PRAGMA journal_mode = MEMORY")


@event.listens_for(Engine, "begin")
def _sqlite_explicit_begin(connection):
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN")


# --- Base du backend pour les tests : SQLite par défaut, Postgres en CI --------
#
# `NEXIS_TEST_BACKEND_DB=postgres` fait tourner tous les tests du backend sur
# un vrai Postgres, comme en production : chaque test reçoit une base neuve,
# créée puis supprimée sur le serveur désigné par `NEXIS_TEST_POSTGRES_URL`
# (une base d'administration dont le nom finit par `_test`). Sans cette
# variable, rien ne change : SQLite jetable dans le dossier du test.

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

_TEST_BACKEND_DB = os.getenv("NEXIS_TEST_BACKEND_DB", "sqlite")


def _postgres_admin_url() -> str:
    url = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
    if not url:
        raise RuntimeError("NEXIS_TEST_BACKEND_DB=postgres exige NEXIS_TEST_POSTGRES_URL")
    if not url.rsplit("/", 1)[-1].split("?", 1)[0].endswith("_test"):
        raise RuntimeError("NEXIS_TEST_POSTGRES_URL doit viser une base jetable dont le nom finit par _test")
    return url


@pytest.fixture
def backend_db_url(tmp_path):
    """URL d'une base vide, propre à ce test."""
    if _TEST_BACKEND_DB == "sqlite":
        yield f"sqlite:///{tmp_path / 'backend.db'}"
        return
    if _TEST_BACKEND_DB != "postgres":
        raise RuntimeError(f"NEXIS_TEST_BACKEND_DB inconnu : {_TEST_BACKEND_DB!r}")

    admin_url = _postgres_admin_url()
    name = f"nexis_t_{uuid.uuid4().hex[:16]}"
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", future=True)
    try:
        with admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{name}"'))
        yield admin_url.rsplit("/", 1)[0] + "/" + name
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()
