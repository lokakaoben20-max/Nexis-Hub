"""Serveur webhook Telegram (telegram_bot/webhook_server.py).

Aucun message perdu, aucun traité deux fois : l'update est traitée avant la
réponse, et le registre Redis (`update_ledger.py`) écarte les renvois.

Requêtes HTTP synthétiques via `aiohttp.test_utils` contre
`build_webhook_app(...)`, sans tunnel ni vrai token Telegram. Le registre
tourne sur un vrai Redis (celui de `docker compose up -d`, et celui de la CI),
car c'est lui qui est partagé entre instances en production. Sans Redis local,
ces tests sont sautés ; la CI n'en tolère aucun sauté.
"""

import asyncio
import importlib
import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp.test_utils import TestClient, TestServer
from redis.asyncio import Redis

from telegram_bot import update_ledger
from telegram_bot.update_ledger import Claim, UpdateLedger

SECRET = "test-secret-token"
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")


def _update(update_id: int = 1) -> dict:
    return {
        "update_id": update_id,
        "message": {
            "message_id": 1,
            "date": 0,
            "chat": {"id": 1, "type": "private"},
            "from": {"id": 1, "is_bot": False, "first_name": "T"},
            "text": "/start",
        },
    }


def _redis_or_skip() -> None:
    async def ping():
        client = Redis.from_url(REDIS_URL)
        try:
            await client.ping()
        finally:
            await client.aclose()

    try:
        asyncio.run(ping())
    except Exception:
        pytest.skip("Redis local injoignable (docker compose up -d redis)")


class Harness:
    """Une app webhook, son dispatcher qui compte les traitements, son registre."""

    def __init__(self, monkeypatch, fail_times: int = 0):
        _redis_or_skip()
        monkeypatch.setenv("WEBHOOK_SECRET_TOKEN", SECRET)
        monkeypatch.setenv("WEBHOOK_PATH", "/webhook")
        from telegram_bot import webhook_server

        self.module = importlib.reload(webhook_server)
        self.bot = Bot(token="123:ABC")
        self.dp = Dispatcher(storage=MemoryStorage())
        self.handled = []
        self._failures_left = fail_times

        @self.dp.message()
        async def _count(message):
            if self._failures_left:
                self._failures_left -= 1
                raise RuntimeError("panne simulée")
            self.handled.append(message.message_id)

        # Identifiant de bot unique : les clés de ce test ne croisent rien d'autre.
        self.bot_id = int(uuid.uuid4().int % 10**12)

    def ledger(self, redis: Redis) -> UpdateLedger:
        return UpdateLedger(redis, self.bot_id)

    async def post(self, redis: Redis, payload=None, secret=SECRET, raw: bytes | None = None):
        app = self.module.build_webhook_app(self.bot, self.dp, ledger=self.ledger(redis))
        headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {}
        async with TestClient(TestServer(app)) as client:
            if raw is not None:
                response = await client.post("/webhook", data=raw, headers=headers)
            else:
                response = await client.post("/webhook", json=payload or _update(), headers=headers)
            return response.status


def _run(scenario):
    async def wrapped():
        redis = Redis.from_url(REDIS_URL)
        try:
            return await scenario(redis)
        finally:
            await redis.aclose()

    return asyncio.run(wrapped())


def test_an_update_is_handled_before_the_answer(monkeypatch):
    h = Harness(monkeypatch)

    async def scenario(redis):
        status = await h.post(redis)
        return status, await redis.get(f"{update_ledger.KEY_PREFIX}:{h.bot_id}:1")

    status, state = _run(scenario)
    assert status == 200
    assert h.handled == [1]
    assert state == b"fait"


def test_a_resent_update_is_not_handled_twice(monkeypatch):
    h = Harness(monkeypatch)

    async def scenario(redis):
        return [await h.post(redis), await h.post(redis)]

    assert _run(scenario) == [200, 200]
    assert h.handled == [1]


def test_a_failed_update_is_answered_with_an_error_then_handled_on_resend(monkeypatch):
    h = Harness(monkeypatch, fail_times=1)

    async def scenario(redis):
        first = await h.post(redis)
        state_after_failure = await redis.get(f"{update_ledger.KEY_PREFIX}:{h.bot_id}:1")
        second = await h.post(redis)
        return first, state_after_failure, second

    first, state_after_failure, second = _run(scenario)
    assert first == 500  # Telegram renverra
    assert state_after_failure is None  # rien de marqué : le renvoi sera traité
    assert second == 200
    assert h.handled == [1]


def test_an_update_being_handled_elsewhere_is_not_handled_again(monkeypatch):
    h = Harness(monkeypatch)

    async def scenario(redis):
        assert await h.ledger(redis).claim(1) is Claim.ACQUIRED  # une autre instance la traite
        return await h.post(redis)

    assert _run(scenario) == 503
    assert h.handled == []


def test_a_wrong_or_missing_secret_is_refused_and_touches_nothing(monkeypatch):
    h = Harness(monkeypatch)

    async def scenario(redis):
        statuses = [await h.post(redis, secret="mauvais"), await h.post(redis, secret=None)]
        return statuses, await redis.exists(f"{update_ledger.KEY_PREFIX}:{h.bot_id}:1")

    statuses, exists = _run(scenario)
    assert statuses == [401, 401]
    assert exists == 0
    assert h.handled == []


def test_a_body_without_update_id_is_refused(monkeypatch):
    h = Harness(monkeypatch)

    async def scenario(redis):
        return [await h.post(redis, payload={"message": {}}), await h.post(redis, raw=b"pas du json")]

    assert _run(scenario) == [400, 400]
    assert h.handled == []


def test_an_update_left_in_progress_by_a_dead_instance_is_handled_after_expiry(monkeypatch):
    h = Harness(monkeypatch)
    monkeypatch.setattr(update_ledger, "PROCESSING_TTL", timedelta(seconds=1))

    async def scenario(redis):
        assert await h.ledger(redis).claim(1) is Claim.ACQUIRED  # instance morte au milieu
        busy = await h.post(redis)
        await asyncio.sleep(1.2)
        return busy, await h.post(redis)

    assert _run(scenario) == (503, 200)
    assert h.handled == [1]


def test_the_webhook_needs_the_shared_redis_registry(monkeypatch):
    monkeypatch.setenv("WEBHOOK_SECRET_TOKEN", SECRET)
    from telegram_bot import webhook_server

    module = importlib.reload(webhook_server)
    with pytest.raises(RuntimeError, match="Redis"):
        module.build_webhook_app(Bot(token="123:ABC"), Dispatcher(storage=MemoryStorage()))


def test_the_webhook_cannot_be_built_without_secret(monkeypatch):
    from telegram_bot import webhook_server

    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", None)
    with pytest.raises(RuntimeError, match="WEBHOOK_SECRET_TOKEN"):
        webhook_server.build_webhook_app(Bot(token="123:ABC"), Dispatcher(storage=MemoryStorage()), ledger=object())


def test_health_endpoint_returns_ok(monkeypatch):
    h = Harness(monkeypatch)

    async def scenario(redis):
        app = h.module.build_webhook_app(h.bot, h.dp, ledger=h.ledger(redis))
        async with TestClient(TestServer(app)) as client:
            response = await client.get("/health")
            return response.status, await response.json()

    assert _run(scenario) == (200, {"status": "ok"})


class _FakeTelegram:
    def __init__(self, registered_url):
        self.registered_url = registered_url
        self.set_calls = []

    async def get_webhook_info(self):
        from types import SimpleNamespace

        return SimpleNamespace(url=self.registered_url, pending_update_count=3)

    async def set_webhook(self, **kwargs):
        self.set_calls.append(kwargs)
        self.registered_url = kwargs["url"]
        return True


def test_the_server_refuses_to_start_when_telegram_sends_elsewhere(monkeypatch):
    from telegram_bot import webhook_server

    monkeypatch.setattr(webhook_server, "WEBHOOK_URL", "https://bot.example.org")
    monkeypatch.setattr(webhook_server, "WEBHOOK_PATH", "/webhook")
    with pytest.raises(RuntimeError, match="webhook_setup"):
        asyncio.run(webhook_server.ensure_webhook_registered(_FakeTelegram("https://ancien.example.org/webhook")))
    asyncio.run(webhook_server.ensure_webhook_registered(_FakeTelegram("https://bot.example.org/webhook")))


def test_the_server_never_registers_the_webhook_itself():
    """Le serveur ne fait que vérifier : l'enregistrement (et donc tout
    effacement d'updates en attente) est réservé à webhook_setup."""
    source = (ROOT / "telegram_bot" / "webhook_server.py").read_text(encoding="utf-8")
    assert "set_webhook(" not in source
    assert "drop_pending_updates" not in source.split('"""', 2)[2]


def test_setup_registers_without_dropping_pending_updates(monkeypatch):
    from telegram_bot import webhook_server, webhook_setup

    monkeypatch.setattr(webhook_server, "WEBHOOK_URL", "https://bot.example.org/")
    monkeypatch.setattr(webhook_server, "WEBHOOK_PATH", "/webhook")
    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", SECRET)
    telegram = _FakeTelegram(None)

    url = asyncio.run(webhook_setup.register(telegram))

    assert url == "https://bot.example.org/webhook"
    assert telegram.set_calls == [
        {"url": "https://bot.example.org/webhook", "secret_token": SECRET, "drop_pending_updates": False}
    ]


def test_run_webhook_requires_webhook_url(monkeypatch):
    from telegram_bot import webhook_server

    # Patch direct des constantes : `load_dotenv()` réinjecterait un vrai
    # WEBHOOK_URL du .env local après un `monkeypatch.delenv`.
    monkeypatch.setattr(webhook_server, "WEBHOOK_URL", None)
    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", SECRET)
    with pytest.raises(RuntimeError, match="WEBHOOK_URL"):
        asyncio.run(webhook_server.run_webhook(Bot(token="123:ABC"), Dispatcher(storage=MemoryStorage())))


def test_run_webhook_requires_secret_token(monkeypatch):
    from telegram_bot import webhook_server

    monkeypatch.setattr(webhook_server, "WEBHOOK_URL", "https://example.org")
    monkeypatch.setattr(webhook_server, "WEBHOOK_SECRET_TOKEN", None)
    with pytest.raises(RuntimeError, match="WEBHOOK_SECRET_TOKEN"):
        asyncio.run(webhook_server.run_webhook(Bot(token="123:ABC"), Dispatcher(storage=MemoryStorage())))
