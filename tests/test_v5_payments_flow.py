import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import main
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

    async def post(self, url, json):
        self.last_request = {"url": url, "json": json}
        return DummyResponse({"status": "ok", "payment_status": json["payment_status"]})


def test_sync_payment_to_backend_posts_payment_status(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)
    result = asyncio.run(backend_client.sync_payment_to_backend(5, "paid_escrow", mission_id=7))
    assert result["status"] == "ok"
    assert result["payment_status"] == "paid_escrow"


class RaisingAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        raise RuntimeError("backend unreachable")


def test_payment_confirmation_survives_backend_outage(monkeypatch):
    # Regression guard: the escrow payment itself already happened locally
    # (mark_quote_paid / mark_quote_paid_with_wallet) by the time this sync
    # runs — if the backend is down, the client/provider must still get their
    # confirmation instead of the handler crashing on this best-effort mirror.
    monkeypatch.setattr(main.httpx, "AsyncClient", RaisingAsyncClient)

    result = asyncio.run(main._safe_backend_call(backend_client.sync_payment_to_backend(5, "paid_escrow", mission_id=7)))

    assert result is None
