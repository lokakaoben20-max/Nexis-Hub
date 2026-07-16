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
        return DummyResponse({"status": "ok", "provider": {"telegram_id": json["telegram_id"]}})


def test_provider_registration_syncs_to_backend(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)
    result = asyncio.run(main.sync_provider_to_backend(321, "Alice", phone_number="+243", services=["service_plomberie"], communes=["Gombe"], language="fr"))
    assert result["status"] == "ok"
    assert result["provider"]["telegram_id"] == 321
