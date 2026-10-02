"""Fixtures communes aux tests du bot.

- Par défaut, tout appel httpx.AsyncClient non simulé par le test échoue
  immédiatement (ConnectError) : le comportement « backend injoignable »,
  sans attendre un timeout. Les tests qui patchent eux-mêmes
  httpx.AsyncClient passent après cette fixture et gardent la main.
- `live_backend` branche à la place le vrai backend V5 (FastAPI + registre
  d'argent) en mémoire, sur une base SQLite jetable : les tests d'argent du
  bot passent par les mêmes règles qu'en production, pas par une imitation.
"""

import importlib
import sqlite3

import httpx
import pytest

import db

_RealAsyncClient = httpx.AsyncClient
TEST_BACKEND_API_KEY = "test-backend-api-key-not-a-secret"


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


class LiveBackend:
    """Le vrai backend en mémoire, et de quoi lire son registre."""

    def __init__(self, database_module):
        self.database = database_module

    def balance(self, telegram_id: int, currency: str = "USD") -> float:
        from backend.app import ledger

        with self.database.SessionLocal() as session:
            return float(ledger.wallet_balances(session, ledger.TELEGRAM, telegram_id)[currency])

    def credit_wallet(self, telegram_id: int, amount: float, currency: str = "USD") -> None:
        from backend.app import ledger

        with self.database.SessionLocal() as session:
            account_id = ledger.account_id_for(session, ledger.TELEGRAM, telegram_id, create=True)
            ledger.record_opening_balance(session, account_id, currency, amount)
            session.commit()

    def mission(self, mission_id: int):
        from backend.app import ledger

        with self.database.SessionLocal() as session:
            return session.get(ledger.BotMission, mission_id)

    def age_status(self, mission_id: int, hours: int) -> None:
        """Fait comme si la mission était dans son statut depuis `hours` heures."""
        from datetime import timedelta

        from backend.app import ledger

        with self.database.SessionLocal() as session:
            mission = session.get(ledger.BotMission, mission_id)
            mission.status_changed_at = mission.status_changed_at - timedelta(hours=hours)
            session.commit()

    def auto_release(self, mission_id: int):
        from backend.app import ledger

        with self.database.SessionLocal() as session:
            return ledger.auto_release(session, mission_id)


@pytest.fixture
def live_backend(tmp_path, monkeypatch):
    # Charge d'abord tout le backend : recharger un module importé pour la
    # première fois juste avant redéfinirait ses tables deux fois.
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'backend.db'}")
    monkeypatch.setenv("BACKEND_API_KEY", TEST_BACKEND_API_KEY)
    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    backend_main = importlib.reload(importlib.import_module("backend.app.main"))
    database_module.init_db()

    class _LiveAsyncClient(_RealAsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.ASGITransport(app=backend_main.app)
            super().__init__(*args, **kwargs)

    from telegram_bot import backend_client

    monkeypatch.setattr(httpx, "AsyncClient", _LiveAsyncClient)
    monkeypatch.setattr(backend_client, "BACKEND_AUTH_HEADERS", {"X-API-Key": TEST_BACKEND_API_KEY})
    return LiveBackend(database_module)
