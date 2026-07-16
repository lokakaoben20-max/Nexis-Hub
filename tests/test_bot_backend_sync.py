import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import main


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyAsyncClient:
    def __init__(self, *args, **kwargs):
        self.last_request = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json):
        self.last_request = {"url": url, "json": json}
        return DummyResponse({"status": "ok", "user": {"telegram_id": json["telegram_id"]}})

    async def get(self, url, params=None):
        self.last_request = {"url": url, "params": params}
        return DummyResponse({"telegram_id": 42, "client": {"telegram_id": 42, "first_name": "Alice"}, "client_missions": [{"mission_id": 1}]})


def test_sync_user_to_backend_posts_payload(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.sync_user_to_backend(42, first_name="Alice", phone_number="+243", language="fr"))

    assert result["status"] == "ok"
    assert result["user"]["telegram_id"] == 42


def test_fetch_backend_profile_returns_payload(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.fetch_backend_profile(42))

    assert result["client"]["first_name"] == "Alice"
    assert result["client_missions"][0]["mission_id"] == 1


def test_persist_client_registration_returns_backend_and_local(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.persist_client_registration(77, first_name="Bob", phone_number="+243", language="fr"))

    assert result["backend"]["status"] == "ok"
    assert result["local"]["telegram_id"] == 77


def test_persist_mission_creation_returns_backend_and_local(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.persist_mission_creation(88, 999, {"service": "service_plomberie", "commune": "Gombe", "currency": "USD"}))

    assert result["backend"]["status"] == "ok"
    assert result["local"]["id"] == 999
