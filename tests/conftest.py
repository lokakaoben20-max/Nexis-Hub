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
        # Notifications que le backend enverrait lui-même par Telegram.
        self.sent = []

    def balance(self, telegram_id: int, currency: str = "USD") -> float:
        from backend.app import ledger

        with self.database.SessionLocal() as session:
            return float(ledger.wallet_balances(session, ledger.account_id_for(session, ledger.TELEGRAM, telegram_id))[currency])

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

    def new_mission(
        self,
        client: int,
        alert=(),
        service: str = "service_menage",
        commune: str = "Gombe",
        currency: str = "USD",
        urgent: bool = False,
        description: str = "Test",
    ) -> int:
        """Mission créée par le backend, comme le ferait le bot ; renvoie son numéro."""
        import uuid

        from backend.app import crud, ledger

        with self.database.SessionLocal() as session:
            mission, _ = crud.create_mission(
                session,
                channel=ledger.TELEGRAM,
                client_external_id=str(client),
                creation_key=uuid.uuid4().hex,
                service=service,
                commune=commune,
                currency=currency,
                description=description,
                urgent=urgent,
                alert_provider_telegram_ids=list(alert),
                destination_latitude=-4.3076,
                destination_longitude=15.3125,
                destination_landmark="Portail bleu après la poste",
            )
            return mission.mission_id

    def quote(self, mission_id: int, provider: int, amount: float = 100.0, currency: str = "USD", delay_hours: int = 2) -> int:
        """Devis envoyé par un prestataire prévenu ; renvoie son numéro."""
        from backend.app import crud

        with self.database.SessionLocal() as session:
            return crud.create_quote(session, mission_id, provider, amount=amount, currency=currency, delay_hours=delay_hours).id

    def accept(self, quote_id: int, client: int) -> None:
        from backend.app import crud, ledger

        with self.database.SessionLocal() as session:
            crud.accept_quote(session, quote_id, ledger.account_id_for(session, ledger.TELEGRAM, client, create=True))

    def quoted_mission(self, client: int, provider: int, amount: float = 100.0, currency: str = "USD", **mission) -> tuple[int, int]:
        """Mission avec un devis en attente : (numéro de mission, numéro de devis)."""
        mission_id = self.new_mission(client, alert=(provider,), currency=currency, **mission)
        return mission_id, self.quote(mission_id, provider, amount=amount, currency=currency)

    def accepted_quote(self, client: int, provider: int, amount: float = 100.0, currency: str = "USD", **mission) -> tuple[int, int]:
        """Mission dont le client a accepté le devis : prête à être payée."""
        mission_id, quote_id = self.quoted_mission(client, provider, amount=amount, currency=currency, **mission)
        self.accept(quote_id, client)
        return mission_id, quote_id

    def completed_mission(self, client: int, provider: int, amount: float = 100.0, **mission) -> int:
        """Mission payée par le wallet, faite et confirmée : le registre a réglé."""
        from backend.app import ledger

        mission_id, quote_id = self.accepted_quote(client, provider, amount=amount, **mission)
        self.credit_wallet(client, amount, mission.get("currency", "USD"))
        with self.database.SessionLocal() as session:
            client_account = ledger.account_id_for(session, ledger.TELEGRAM, client)
            provider_account = ledger.account_id_for(session, ledger.TELEGRAM, provider)
            ledger.fund_mission(session, mission_id, method="wallet", client_account_id=client_account, quote_id=quote_id)
            ledger.start_mission(session, mission_id, provider_account)
            ledger.finish_mission(session, mission_id, provider_account)
            ledger.confirm_completion(session, mission_id, client_account)
        return mission_id

    def get_quote(self, quote_id: int):
        from backend.app.models import BotQuote

        with self.database.SessionLocal() as session:
            return session.get(BotQuote, quote_id)

    def disputed_ids(self) -> list[int]:
        from backend.app import crud

        with self.database.SessionLocal() as session:
            return [mission.mission_id for mission in crud.admin_missions(session, status="disputed")]

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
def live_backend(monkeypatch, backend_db_url):
    # Charge d'abord tout le backend : recharger un module importé pour la
    # première fois juste avant redéfinirait ses tables deux fois.
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TEST_BACKEND_API_KEY)
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
    live = LiveBackend(database_module)
    tasks_module = importlib.import_module("backend.app.tasks")
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda chat_id, text, reply_markup=None: live.sent.append((chat_id, text)))
    return live
