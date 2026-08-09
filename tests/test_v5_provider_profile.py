import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from telegram_bot import backend_client


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

    async def get(self, url, params=None):
        self.last_request = {"url": url, "params": params}
        return DummyResponse({"telegram_id": 777, "provider": {"telegram_id": 777, "full_name": "Bob", "phone_number": "+243", "status": "available", "services": ["service_plomberie"]}})


def test_provider_profile_uses_backend_payload(monkeypatch):
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", DummyAsyncClient)
    result = asyncio.run(backend_client.fetch_backend_profile(777))
    assert result["provider"]["full_name"] == "Bob"
