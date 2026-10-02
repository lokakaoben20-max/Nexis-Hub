"""Fixtures communes aux tests du backend.

Les tests rechargent le backend sur une base SQLite jetable (tmp_path).

- Sous Windows, chaque commit SQLite sur disque (fsync) coûtait ~0,1 s ; on
  coupe la durabilité de ces bases de test, pas la logique.
- Le pilote sqlite3 gère lui-même ses transactions et casse les SAVEPOINT
  (un RELEASE validait tout). Le registre d'argent s'appuie dessus
  (`begin_nested`) : on applique la correction documentée par SQLAlchemy pour
  que SQLite se comporte comme Postgres (transaction ouverte par BEGIN,
  savepoints imbriqués réels).
"""

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _sqlite_for_tests(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.isolation_level = None
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        cursor.close()


@event.listens_for(Engine, "begin")
def _sqlite_explicit_begin(connection):
    if connection.dialect.name == "sqlite":
        connection.exec_driver_sql("BEGIN")
