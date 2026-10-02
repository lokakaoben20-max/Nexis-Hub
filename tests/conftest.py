"""Fixtures communes aux tests du bot.

Sans API backend lancée sur 127.0.0.1:8000, chaque appel de
telegram_bot/backend_client.py attendait son timeout avant que le bot ne se
rabatte sur db.py -- la suite complète prenait ~35 min. Ici, tout appel
httpx.AsyncClient non simulé par le test échoue immédiatement (ConnectError),
ce qui reproduit le même repli sans l'attente. Les tests qui patchent
eux-mêmes httpx.AsyncClient passent après cette fixture et gardent la main.
"""

import sqlite3

import httpx
import pytest

import db

_RealAsyncClient = httpx.AsyncClient


def _refuse(request: httpx.Request) -> httpx.Response:
    raise httpx.ConnectError("backend désactivé pendant les tests", request=request)


class _OfflineAsyncClient(_RealAsyncClient):
    def __init__(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_refuse)
        super().__init__(*args, **kwargs)


@pytest.fixture(autouse=True)
def _backend_offline(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", _OfflineAsyncClient)


@pytest.fixture(autouse=True)
def _fast_sqlite(monkeypatch):
    """Sous Windows, chaque écriture SQLite sur disque (fsync du fichier et de
    son journal) coûtait ~0,1 s -- l'essentiel de la durée de la suite. Les
    bases de test sont jetables : on coupe la durabilité, pas la logique."""
    def get_connection():
        conn = sqlite3.connect(db.DB_PATH)
        conn.execute("PRAGMA synchronous = OFF")
        conn.execute("PRAGMA journal_mode = MEMORY")
        return conn

    monkeypatch.setattr(db, "get_connection", get_connection)
