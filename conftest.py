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
