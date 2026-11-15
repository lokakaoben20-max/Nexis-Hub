"""Surveillance de l'adresse publique du webhook (telegram_bot/webhook_watch.py).

Une coupure (tunnel sans connexion, 530 de Cloudflare) prévient les admins
une seule fois, même avec plusieurs instances ; le retour envoie un seul
« rétabli ». L'état partagé vit dans un vrai Redis, comme en production
(sauté sans Redis local ; la CI n'en tolère aucun sauté). Les clients
HTTP des tests ignorent le proxy de la machine (trust_env=False).
"""

import asyncio
import importlib
import os
import sys
import uuid
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp.test_utils import TestServer
from redis.asyncio import Redis

from telegram_bot import webhook_watch
from telegram_bot.update_ledger import UpdateLedger

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
URL = "https://nexis.example/webhook"
# Le vrai client : conftest.py remplace httpx.AsyncClient par un client hors
# ligne pendant chaque test, ce qui fausserait la sonde.
RealAsyncClient = httpx.AsyncClient


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


class FakeBot:
    def __init__(self, registered_url: str = URL):
        self.id = int(uuid.uuid4().int % 10**9)  # clés Redis propres à chaque test
        self.registered_url = registered_url
        self.sent: list[tuple[int, str]] = []

    async def get_webhook_info(self):
        return SimpleNamespace(url=self.registered_url)

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class Public:
    """Ce que répond l'adresse publique : le bot (401) ou Cloudflare (530)."""

    def __init__(self):
        self.up = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        assert "X-Telegram-Bot-Api-Secret-Token" not in request.headers
        if self.up:
            return httpx.Response(401, text="Unauthorized")
        return httpx.Response(530, text="error code: 1033")


@pytest.fixture
def admins(monkeypatch):
    async def ids():
        return [11, 22]

    async def language(person):
        return {11: "fr", 22: "en"}[person]

    monkeypatch.setattr(webhook_watch.backend_client, "admin_telegram_ids", ids)
    monkeypatch.setattr(webhook_watch.backend_client, "get_language", language)


def _run(scenario):
    _redis_or_skip()

    async def wrapped():
        redis = Redis.from_url(REDIS_URL)
        try:
            await scenario(redis)
        finally:
            await redis.aclose()

    asyncio.run(wrapped())


def _watch(bot, redis, public):
    http = RealAsyncClient(transport=httpx.MockTransport(public.handler), trust_env=False)
    return webhook_watch.WebhookWatch(bot, redis, URL, http)


def test_an_outage_alerts_each_admin_once_in_their_language_then_recovery(admins):
    async def scenario(redis):
        bot, public = FakeBot(), Public()
        watch = _watch(bot, redis, public)

        await watch.check_once()
        assert bot.sent == []

        public.up = False
        await watch.check_once()
        assert bot.sent == []  # un seul échec : peut-être un raté passager
        await watch.check_once()
        assert [chat for chat, _ in bot.sent] == [11, 22]
        assert "injoignable" in bot.sent[0][1] and "HTTP 530" in bot.sent[0][1]
        assert "unreachable" in bot.sent[1][1]

        await watch.check_once()
        await watch.check_once()
        assert len(bot.sent) == 2  # pas de nouvelle alerte tant que dure la coupure

        public.up = True
        await watch.check_once()
        assert [chat for chat, _ in bot.sent[2:]] == [11, 22]
        assert "de nouveau joignable" in bot.sent[2][1]

        await watch.check_once()
        assert len(bot.sent) == 4

    _run(scenario)


def test_two_instances_send_a_single_alert_and_a_single_recovery(admins):
    async def scenario(redis):
        bot, public = FakeBot(), Public()
        first, second = _watch(bot, redis, public), _watch(bot, redis, public)

        public.up = False
        for _ in range(2):
            await first.check_once()
            await second.check_once()
        assert len(bot.sent) == 2  # 2 admins, une seule alerte chacun

        public.up = True
        await first.check_once()
        await second.check_once()
        assert len(bot.sent) == 4

    _run(scenario)


def test_a_webhook_registered_elsewhere_is_an_outage(admins):
    async def scenario(redis):
        bot = FakeBot(registered_url="")
        watch = _watch(bot, redis, Public())
        await watch.check_once()
        await watch.check_once()
        assert len(bot.sent) == 2
        assert "webhook enregistré ailleurs (aucun)" in bot.sent[0][1]

    _run(scenario)


def test_a_timeout_counts_as_an_outage():
    def timeout(request):
        raise httpx.ConnectTimeout("lent", request=request)

    async def scenario():
        async with RealAsyncClient(transport=httpx.MockTransport(timeout), trust_env=False) as http:
            assert await webhook_watch.probe_public_url(URL, http) == "délai dépassé"

    asyncio.run(scenario())


def test_the_probe_recognises_the_real_webhook_server_and_nothing_else(monkeypatch):
    """La sonde accepte la vraie réponse du serveur webhook (sans secret),
    et rien n'est traité ni inscrit au registre."""
    _redis_or_skip()
    monkeypatch.setenv("WEBHOOK_SECRET_TOKEN", "secret-test")
    monkeypatch.setenv("WEBHOOK_PATH", "/webhook")
    from telegram_bot import webhook_server

    module = importlib.reload(webhook_server)

    async def scenario():
        redis = Redis.from_url(REDIS_URL)
        bot = Bot(token="123:ABC")
        dp = Dispatcher(storage=MemoryStorage())
        handled = []

        @dp.message()
        async def count(message):
            handled.append(message)

        app = module.build_webhook_app(bot, dp, ledger=UpdateLedger(redis, 987654))
        server = TestServer(app)
        await server.start_server()
        try:
            async with RealAsyncClient(trust_env=False) as http:
                url = str(server.make_url("/webhook"))
                assert await webhook_watch.probe_public_url(url, http) is None
                other = str(server.make_url("/ailleurs"))
                assert await webhook_watch.probe_public_url(other, http) == "réponse HTTP 404"
        finally:
            await server.close()
            await bot.session.close()
            await redis.aclose()
        assert handled == []

    asyncio.run(scenario())


def test_a_bad_interval_setting_refuses_to_start(monkeypatch):
    monkeypatch.setenv("WEBHOOK_WATCH_INTERVAL_SECONDS", "deux minutes")
    with pytest.raises(RuntimeError):
        webhook_watch.interval_seconds()
    monkeypatch.setenv("WEBHOOK_WATCH_INTERVAL_SECONDS", "-5")
    with pytest.raises(RuntimeError):
        webhook_watch.interval_seconds()
    monkeypatch.delenv("WEBHOOK_WATCH_INTERVAL_SECONDS")
    assert webhook_watch.interval_seconds() == webhook_watch.DEFAULT_INTERVAL_SECONDS
