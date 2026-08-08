import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import db
import main
from telegram_bot import backend_client, keyboards, payment


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

    async def post(self, url, json=None):
        self.last_request = {"url": url, "json": json}
        if url.endswith("/api/bot/quotes"):
            return DummyResponse({"status": "ok", "quote": {"id": 501, **json}})
        if "/quotes/" in url and url.endswith("/accept"):
            return DummyResponse({"status": "ok", "quote": {"id": 501, "status": "accepted"}})
        if "/quotes/" in url and url.endswith("/reject"):
            return DummyResponse({"status": "ok", "quote": {"id": 501, "status": "rejected"}})
        telegram_id = json["telegram_id"] if json else None
        return DummyResponse({"status": "ok", "user": {"telegram_id": telegram_id}})

    async def get(self, url, params=None):
        self.last_request = {"url": url, "params": params}
        return DummyResponse({"telegram_id": 42, "client": {"telegram_id": 42, "first_name": "Alice"}, "client_missions": [{"mission_id": 1}]})

    async def patch(self, url, json):
        self.last_request = {"url": url, "json": json}
        return DummyResponse({"status": "ok", "provider": {"telegram_id": 1, **json}})


class RaisingAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        raise RuntimeError("backend unreachable")

    async def get(self, url, params=None):
        raise RuntimeError("backend unreachable")

    async def patch(self, url, json=None):
        raise RuntimeError("backend unreachable")


def test_sync_user_to_backend_posts_payload(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.sync_user_to_backend(42, first_name="Alice", phone_number="+243", language="fr"))

    assert result["status"] == "ok"
    assert result["user"]["telegram_id"] == 42


def test_fetch_backend_profile_returns_payload(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.fetch_backend_profile(42))

    assert result["client"]["first_name"] == "Alice"
    assert result["client_missions"][0]["mission_id"] == 1


def test_persist_client_registration_returns_backend_and_local(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.persist_client_registration(77, first_name="Bob", phone_number="+243", language="fr"))

    assert result["backend"]["status"] == "ok"
    assert result["local"]["telegram_id"] == 77


def test_persist_mission_creation_returns_backend_and_local(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.persist_mission_creation(88, 999, {"service": "service_plomberie", "commune": "Gombe", "currency": "USD"}))

    assert result["backend"]["status"] == "ok"
    assert result["local"]["id"] == 999


def test_persist_mission_creation_survives_backend_outage(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", RaisingAsyncClient)

    result = asyncio.run(backend_client.persist_mission_creation(88, 999, {"service": "service_plomberie", "commune": "Gombe", "currency": "USD"}))

    assert result["backend"] is None
    assert result["local"]["id"] == 999


def test_sync_provider_status_to_backend_patches_status(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.sync_provider_status_to_backend(1, "offline"))

    assert result["status"] == "ok"
    assert result["provider"]["status"] == "offline"


def test_sync_user_language_to_backend_patches_language(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.sync_user_language_to_backend(1, "ln"))

    assert result["status"] == "ok"


def test_sync_provider_language_to_backend_patches_language(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.sync_provider_language_to_backend(1, "en"))

    assert result["provider"]["language"] == "en"


def test_sync_provider_services_to_backend_patches_services(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.sync_provider_services_to_backend(1, ["service_peinture"]))

    assert result["provider"]["services"] == ["service_peinture"]


def test_sync_provider_ignored_increment_and_reset_to_backend(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    increment_result = asyncio.run(backend_client.sync_provider_ignored_increment_to_backend(1))
    reset_result = asyncio.run(backend_client.sync_provider_ignored_reset_to_backend(1))

    assert increment_result["status"] == "ok"
    assert reset_result["status"] == "ok"


def test_safe_backend_call_swallows_network_errors(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", RaisingAsyncClient)

    result = asyncio.run(main._safe_backend_call(backend_client.sync_provider_status_to_backend(1, "available")))

    assert result is None


def test_get_user_language_prefers_backend_value(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    db.create_user(42, "+243800000042", "Alice", language="fr")
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)
    # get_user_language résout fetch_backend_profile dans son propre module
    # (telegram_bot.backend_client) — patcher main.fetch_backend_profile n'a
    # aucun effet dessus, même si `main` réexporte le même nom.
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return({"client": {"language": "en"}}))

    result = asyncio.run(backend_client.get_user_language(42))

    assert result == "en"


def test_get_user_language_falls_back_to_local_db_when_backend_unavailable(tmp_path, monkeypatch):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    db.create_user(42, "+243800000042", "Alice", language="ln")
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))

    result = asyncio.run(backend_client.get_user_language(42))

    assert result == "ln"


def test_get_provider_language_prefers_backend_value(monkeypatch, tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    db.create_provider(2, "+243800000002", "Bob", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return({"provider": {"language": "en"}}))

    result = asyncio.run(backend_client.get_provider_language(2))

    assert result == "en"


def test_get_provider_language_falls_back_to_local_db_when_backend_unavailable(tmp_path, monkeypatch):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    db.create_provider(2, "+243800000002", "Bob", ["service_plomberie"], ["Gombe"], language="ln")
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))

    result = asyncio.run(backend_client.get_provider_language(2))

    assert result == "ln"


async def _async_return(value):
    return value


def test_sync_quote_to_backend_posts_payload(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(backend_client.sync_quote_to_backend(
        mission_id=1001, provider_telegram_id=7, amount=50.0, currency="USD", delay_hours=2, message="ok",
    ))

    assert result["status"] == "ok"
    assert result["quote"]["id"] == 501
    assert result["quote"]["mission_id"] == 1001


def test_sync_quote_accept_and_reject_to_backend(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    accept_result = asyncio.run(backend_client.sync_quote_accept_to_backend(501))
    reject_result = asyncio.run(backend_client.sync_quote_reject_to_backend(501))

    assert accept_result["quote"]["status"] == "accepted"
    assert reject_result["quote"]["status"] == "rejected"


def test_parse_quote_callback_ids_with_backend_id():
    local_id, backend_id = keyboards._parse_quote_callback_ids("5:501")

    assert local_id == 5
    assert backend_id == 501


def test_parse_quote_callback_ids_without_backend_id():
    local_id, backend_id = keyboards._parse_quote_callback_ids("5:-")

    assert local_id == 5
    assert backend_id is None


class DummyState:
    def __init__(self):
        self.cleared = False

    async def clear(self):
        self.cleared = True


def test_finalize_review_clears_state_after_backend_success(monkeypatch):
    async def save_review(*args, **kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(payment, "sync_review_to_backend", save_review)
    state = DummyState()

    result = asyncio.run(payment._finalize_review(42, {"rating_mission_id": 1, "rating_value": 5}, "Excellent", state))

    assert result == {"status": "ok"}
    assert state.cleared is True


def test_finalize_review_keeps_state_when_backend_is_unavailable(monkeypatch):
    async def save_review(*args, **kwargs):
        raise RuntimeError("backend unreachable")

    monkeypatch.setattr(payment, "sync_review_to_backend", save_review)
    state = DummyState()

    result = asyncio.run(payment._finalize_review(42, {"rating_mission_id": 1, "rating_value": 5}, None, state))

    assert result is None
    assert state.cleared is False


def test_backend_mission_is_rendered_without_legacy_only_fields():
    mission = {
        "mission_id": 17,
        "service": "service_plomberie",
        "commune": "Gombe",
        "status": "completed",
        "payment_status": "released",
    }

    rendered = main.format_mission_client(mission)
    rich_message = main.build_history_rich_message("fr", [mission])

    assert "NXH-0017" in rendered
    assert "Non attribué" in rendered
    assert rich_message.blocks


def test_sync_provider_verified_to_backend(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.sync_provider_verified_to_backend(1))

    assert result["status"] == "ok"


def test_sync_provider_suspended_to_backend(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.sync_provider_suspended_to_backend(1))

    assert result["status"] == "ok"


def test_sync_provider_unsuspended_to_backend(monkeypatch):
    monkeypatch.setattr(main.httpx, "AsyncClient", DummyAsyncClient)

    result = asyncio.run(main.sync_provider_unsuspended_to_backend(1))

    assert result["status"] == "ok"
