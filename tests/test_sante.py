"""Santé « vivant » / « prêt » du backend, de la Mini App et du bot webhook,
et refus de démarrer hors développement quand la configuration manque."""

import asyncio
import importlib
import os

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("BOT_TOKEN", "123:ABC")


@pytest.fixture
def backend(monkeypatch, backend_db_url):
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.delenv("APP_ENV", raising=False)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    yield main, database
    database.engine.dispose()


def _version(database, revision):
    with database.engine.begin() as connexion:
        connexion.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connexion.execute(text("DELETE FROM alembic_version"))
        connexion.execute(text("INSERT INTO alembic_version (version_num) VALUES (:r)"), {"r": revision})


def test_le_backend_n_est_pret_que_sur_une_base_a_la_derniere_migration(backend):
    main, database = backend
    from backend.app import sante

    client = TestClient(main.app)
    assert client.get("/health/live").status_code == 200

    jamais = client.get("/health/ready")
    assert jamais.status_code == 503
    assert "jamais migrée" in jamais.json()["problemes"][0]

    _version(database, "0a1b2c3d4e5f")  # une migration en retard
    assert client.get("/health/ready").status_code == 503

    _version(database, sante.revision_attendue())
    assert client.get("/health/ready").json() == {"status": "ok"}


def test_le_backend_refuse_de_demarrer_en_production_sans_configuration(backend, monkeypatch):
    main, _ = backend
    monkeypatch.setenv("APP_ENV", "production")
    for nom in ("BACKEND_API_KEY_TELEGRAM", "APP_CODE_HMAC_KEY", "PAYMENT_GATEWAY", "COLLECTION_FEE_RATE"):
        monkeypatch.delenv(nom, raising=False)
    import nexis_config

    with pytest.raises(nexis_config.ConfigurationInvalide):
        with TestClient(main.app):
            pass


def test_la_mini_app_n_est_prete_que_si_le_backend_repond(monkeypatch):
    import mini_app.app as mini_app

    client = TestClient(mini_app.app)
    assert client.get("/health/live").status_code == 200
    # Les tests coupent tout appel réseau sortant : backend injoignable.
    assert client.get("/health/ready").status_code == 503

    reel = httpx.AsyncClient.__mro__[1]  # le vrai client, sous la coupure réseau des tests

    class BackendVivant(reel):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(lambda requete: httpx.Response(200, json={"status": "ok"}))
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", BackendVivant)
    assert client.get("/health/ready").json() == {"status": "ok"}


class _Registre:
    def __init__(self, vivant):
        self.vivant = vivant

    async def ping(self):
        if not self.vivant:
            raise ConnectionError("redis coupé")


@pytest.mark.parametrize("vivant, attendu", [(True, 200), (False, 503)])
def test_le_bot_n_est_pret_que_si_redis_repond(monkeypatch, vivant, attendu):
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiohttp.test_utils import TestClient as ClientAiohttp
    from aiohttp.test_utils import TestServer

    from telegram_bot import webhook_server

    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", "s" * 40)
    app = webhook_server.build_webhook_app(Bot(token="123:ABC"), Dispatcher(storage=MemoryStorage()), ledger=_Registre(vivant))

    async def lire():
        async with ClientAiohttp(TestServer(app)) as client:
            return (await client.get("/health/live")).status, (await client.get("/health/ready")).status

    assert asyncio.run(lire()) == (200, attendu)
