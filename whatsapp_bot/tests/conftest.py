"""Banc d'essai du service WhatsApp : le vrai service, le vrai backend (base
jetable, comme les autres tests du backend), un faux Meta et un vrai Redis,
reliés dans le même processus par `httpx.ASGITransport`. Rien ne sort sur
le réseau.

Redis : celui de `docker compose up -d` sur le PC, celui de la CI. Sans
Redis local, ces tests sont sautés ; la CI n'en tolère aucun sauté.
"""

from __future__ import annotations

import asyncio
import importlib
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from redis.asyncio import Redis

from whatsapp_bot.app import Service, build_app
from whatsapp_bot.backend import Backend
from whatsapp_bot.conversation import Conversation, Links
from whatsapp_bot.fake_meta import FakeMeta
from whatsapp_bot.meta import CloudApi
from whatsapp_bot.store import Store

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-0001"
WHATSAPP_KEY = "test-whatsapp-service-key-not-a-secret-0002"
APP_SECRET = "test-app-secret-not-a-secret-000000000001"
VERIFY_TOKEN = "test-verify-token-not-a-secret-00000000001"
ACCESS_TOKEN = "test-access-token-not-a-secret"
PHONE_NUMBER_ID = "100000000000001"
GRAPH_URL = "https://graph.facebook.test/v23.0"
BACKEND_URL = "http://backend.test"


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


@pytest.fixture
def backend_main(backend_db_url, monkeypatch):
    # Charge d'abord tout le backend : recharger un module importé pour la
    # première fois juste avant redéfinirait ses tables deux fois.
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    main.database = database
    return main


def publish_terms(main, version: str = "2026-11-20", *, at: datetime | None = None, documents=("cgu", "conditions_prestataires")) -> None:
    """Publie les conditions (le backend refuse toute inscription tant que
    les documents exigés, prestataires compris, ne sont pas publiés)."""
    from backend.app import conditions

    at = at or datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)
    with main.database.SessionLocal() as db:
        for key in documents:
            conditions.publish_version(db, key, version, f"Texte {key}, version {version}.", effective_at=at, now=at)
        db.commit()


class Bench:
    """Un client WhatsApp qui écrit au service, et ce que le service répond."""

    def __init__(self, main, *, links: Links | None = None):
        self.main = main
        self.fake = FakeMeta(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID, app_secret=APP_SECRET)
        self.links = links or Links(
            telegram_bot="https://t.me/NexisHubBot",
            mini_app="https://nexis.example/app/",
            public_site="https://nexis.example",
        )
        self.prefix = f"nexis_wa_test_{uuid.uuid4().hex[:12]}"
        self.backend_down = False
        self.redis = None
        self.store = None
        self.app = None

    async def __aenter__(self):
        self.redis = Redis.from_url(REDIS_URL)
        self.store = Store(self.redis, prefix=self.prefix)
        bench = self

        async def backend_transport(request):
            if bench.backend_down:
                raise httpx.ConnectError("backend coupé", request=request)
            return await asgi_backend.handle_async_request(request)

        asgi_backend = httpx.ASGITransport(app=self.main.app)
        self.service = Service(
            app_secret=APP_SECRET,
            verify_token=VERIFY_TOKEN,
            phone_number_id=PHONE_NUMBER_ID,
            store=self.store,
            messenger=CloudApi(GRAPH_URL, PHONE_NUMBER_ID, ACCESS_TOKEN, transport=httpx.ASGITransport(app=self.fake.app())),
            conversation=Conversation(
                Backend(BACKEND_URL, WHATSAPP_KEY, transport=_Transport(backend_transport)),
                self.links,
            ),
        )
        self.app = build_app(self.service)
        return self

    async def __aexit__(self, *exc):
        keys = [key async for key in self.redis.scan_iter(f"{self.prefix}:*")]
        if keys:
            await self.redis.delete(*keys)
        await self.redis.aclose()

    async def post(self, payload: dict, *, signed: bool = True, body: bytes | None = None, headers: dict | None = None):
        raw, signed_headers = self.fake.signed(payload)
        if body is not None:
            raw = body
        sent_headers = headers if headers is not None else (signed_headers if signed else {"Content-Type": "application/json"})
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="http://whatsapp.test") as client:
            return await client.post("/webhook", content=raw, headers=sent_headers)

    async def say(self, text: str, **who) -> list:
        return await self._exchange(self.fake.text_message(text, **who))

    async def tap(self, choice: str, **who) -> list:
        return await self._exchange(self.fake.choice_message(choice, list_row=choice.startswith("menu:"), **who))

    async def _exchange(self, payload: dict) -> list:
        before = len(self.fake.sent)
        response = await self.post(payload)
        assert response.status_code == 200, response.text
        return self.fake.sent[before:]

    async def register(self, name: str = "Mado", language: str = "fr", **who) -> list:
        await self.say("Bonjour", **who)
        await self.tap(f"lang:{language}", **who)
        await self.say(name, **who)
        return await self.tap("terms:accept", **who)


class _Transport(httpx.AsyncBaseTransport):
    """Transport fait d'une fonction (le backend, qu'on peut couper)."""

    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request):
        return await self._handler(request)


@pytest.fixture
def bench(backend_main):
    _redis_or_skip()
    publish_terms(backend_main)
    return Bench(backend_main)


def run(scenario):
    return asyncio.run(scenario())
