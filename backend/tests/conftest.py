"""Fixtures communes aux tests du backend.

Les tests rechargent le backend sur une base SQLite jetable (tmp_path). Sous
Windows, chaque commit SQLite sur disque (fsync) coûtait ~0,1 s ; on coupe la
durabilité de ces bases de test, pas la logique.
"""

import sqlite3

from sqlalchemy import event
from sqlalchemy.engine import Engine


@event.listens_for(Engine, "connect")
def _fast_sqlite(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA synchronous = OFF")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        cursor.close()
