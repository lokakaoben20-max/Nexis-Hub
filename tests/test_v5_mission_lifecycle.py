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
        return DummyResponse({"status": "ok", "mission": {"mission_id": json["mission_id"], "status": json["status"]}})


def test_sync_mission_status_to_backend_posts_status(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)
    result = asyncio.run(main.sync_mission_status_to_backend(10, "in_progress"))
    assert result["status"] == "ok"
    assert result["mission"]["status"] == "in_progress"
