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


import pytest  # noqa: E402

# Clé de test du code de présence (backend.app.presence) : sans elle, le
# backend refuse de donner ou de vérifier un code. Jamais une vraie clé.
TEST_PRESENCE_CODE_KEY = "test-presence-key-not-a-secret-0123456789abcdef"


@pytest.fixture(autouse=True)
def _presence_code_key(monkeypatch):
    monkeypatch.setenv("PRESENCE_CODE_KEY", TEST_PRESENCE_CODE_KEY)


@pytest.fixture(autouse=True)
def _no_real_telegram(monkeypatch):
    """Aucun test n'écrit à Telegram, même avec un vrai BOT_TOKEN dans le .env
    du poste : les messages du backend partent dans le vide (un test qui veut
    les lire remplace backend.app.notify.send_telegram_message)."""
    from backend.app import notify

    monkeypatch.setattr(notify, "BOT_TOKEN", "")
