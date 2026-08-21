"""Serveur webhook Telegram (telegram_bot/webhook_server.py).

Vérifie le câblage (validation du secret, endpoint de santé) sans dépendre
d'un tunnel ni d'un vrai token Telegram : `aiohttp.test_utils.TestClient`/
`TestServer` postent des requêtes HTTP synthétiques contre
`build_webhook_app(...)` directement, sans binder de vrai port. Même style
que le reste de la suite (`asyncio.run(...)` dans des `def test_...():`
classiques) — le projet n'a pas `pytest-asyncio`.
"""

import asyncio
import importlib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp.test_utils import TestClient, TestServer

SECRET = "test-secret-token"

UPDATE_PAYLOAD = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 0,
        "chat": {"id": 1, "type": "private"},
        "from": {"id": 1, "is_bot": False, "first_name": "T"},
        "text": "/start",
    },
}


def _build_app(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_TOKEN", SECRET)
    monkeypatch.setenv("WEBHOOK_PATH", "/webhook")
    # Les constantes du module (WEBHOOK_SECRET_TOKEN, WEBHOOK_PATH) sont lues
    # au niveau module, à l'import — même pattern que keyboards.py/MINI_APP_URL.
    # Il faut recharger le module après avoir posé les variables d'env pour
    # que build_webhook_app les prenne en compte.
    from telegram_bot import webhook_server

    importlib.reload(webhook_server)

    bot = Bot(token="123:ABC")
    dp = Dispatcher(storage=MemoryStorage())
    return webhook_server.build_webhook_app(bot, dp)


async def _post_update(app, headers=None):
    async with TestClient(TestServer(app)) as client:
        response = await client.post("/webhook", json=UPDATE_PAYLOAD, headers=headers or {})
        return response.status


async def _get_health(app):
    async with TestClient(TestServer(app)) as client:
        response = await client.get("/health")
        return response.status, await response.json()


def test_webhook_accepts_request_with_correct_secret(monkeypatch):
    app = _build_app(monkeypatch)

    status = asyncio.run(_post_update(app, headers={"X-Telegram-Bot-Api-Secret-Token": SECRET}))

    assert status == 200


def test_webhook_rejects_request_without_secret_header(monkeypatch):
    app = _build_app(monkeypatch)

    status = asyncio.run(_post_update(app))

    assert status == 401


def test_webhook_rejects_request_with_wrong_secret(monkeypatch):
    app = _build_app(monkeypatch)

    status = asyncio.run(_post_update(app, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"}))

    assert status == 401


def test_health_endpoint_returns_ok(monkeypatch):
    app = _build_app(monkeypatch)

    status, payload = asyncio.run(_get_health(app))

    assert status == 200
    assert payload == {"status": "ok"}


def test_run_webhook_requires_webhook_url(monkeypatch):
    from telegram_bot import webhook_server

    # Patch direct des constantes du module plutôt qu'un reload piloté par
    # les variables d'env : si le vrai .env local a WEBHOOK_URL/
    # WEBHOOK_SECRET_TOKEN posés (test manuel avec un tunnel réel),
    # `load_dotenv()` (non-override par défaut) les réinjecterait après un
    # `monkeypatch.delenv`, et ce test appellerait alors le vrai Telegram.
    monkeypatch.setattr(webhook_server, "WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", SECRET)

    bot = Bot(token="123:ABC")
    dp = Dispatcher(storage=MemoryStorage())
    try:
        asyncio.run(webhook_server.run_webhook(bot, dp))
        assert False, "devait lever RuntimeError"
    except RuntimeError as error:
        assert "WEBHOOK_URL" in str(error)


def test_run_webhook_requires_secret_token(monkeypatch):
    from telegram_bot import webhook_server

    monkeypatch.setattr(webhook_server, "WEBHOOK_URL", "https://example.ngrok-free.app")
    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", None)

    bot = Bot(token="123:ABC")
    dp = Dispatcher(storage=MemoryStorage())
    try:
        asyncio.run(webhook_server.run_webhook(bot, dp))
        assert False, "devait lever RuntimeError"
    except RuntimeError as error:
        assert "WEBHOOK_SECRET_TOKEN" in str(error)
