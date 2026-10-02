"""File d'attente des appels backend qui déplacent de l'argent : un appel
perdu pendant une panne du backend doit être rejoué, dans l'ordre."""

import asyncio

import httpx

import db
from telegram_bot import backend_client
from telegram_bot.dashboard import wallet_balances


class RecordingAsyncClient:
    """Faux backend : répond `status_for(path, payload)` et note chaque POST."""

    posts = []
    status_for = staticmethod(lambda path, payload: 200)

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        path = url.replace(backend_client.BACKEND_BASE_URL, "")
        status = RecordingAsyncClient.status_for(path, json)
        if status is None:
            raise httpx.ConnectError("backend coupé")
        RecordingAsyncClient.posts.append((path, json))
        return httpx.Response(status, json={"status": "ok"}, request=httpx.Request("POST", url))


def _setup(tmp_path, monkeypatch, status_for):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    RecordingAsyncClient.posts = []
    RecordingAsyncClient.status_for = staticmethod(status_for)
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", RecordingAsyncClient)


def test_call_made_while_backend_down_is_kept_then_replayed(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, lambda path, payload: None)

    sent = asyncio.run(backend_client.queue_mission_status(11, "completed", payment_status="released"))

    assert sent is False
    assert db.count_backend_outbox() == 1
    assert backend_client.backend_wallet_sync_pending() is True

    RecordingAsyncClient.status_for = staticmethod(lambda path, payload: 200)
    assert asyncio.run(backend_client.flush_backend_outbox()) is True
    assert RecordingAsyncClient.posts == [
        ("/api/bot/missions/status", {"mission_id": 11, "status": "completed", "payment_status": "released"})
    ]
    assert db.count_backend_outbox() == 0


def test_new_call_waits_behind_older_pending_ones(tmp_path, monkeypatch):
    # Un vieux "in_progress" envoyé après "completed" ferait reculer la mission.
    _setup(tmp_path, monkeypatch, lambda path, payload: None)
    asyncio.run(backend_client.queue_mission_status(12, "in_progress"))

    RecordingAsyncClient.status_for = staticmethod(lambda path, payload: 200)
    asyncio.run(backend_client.queue_mission_status(12, "completed", payment_status="released"))

    assert [payload["status"] for _, payload in RecordingAsyncClient.posts] == ["in_progress", "completed"]
    assert db.count_backend_outbox() == 0


def test_server_error_keeps_the_call_and_stops_the_queue(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, lambda path, payload: 503)
    asyncio.run(backend_client.queue_mission_status(13, "in_progress"))
    asyncio.run(backend_client.queue_mission_status(13, "awaiting_confirmation"))

    assert db.count_backend_outbox() == 2
    # La file s'arrête au premier échec : le second appel n'est même pas tenté.
    assert [payload["status"] for _, payload in RecordingAsyncClient.posts] == ["in_progress", "in_progress"]


def test_definitive_refusal_is_dropped_so_it_does_not_block_the_queue(tmp_path, monkeypatch):
    # 409 mission_already_settled : rejouer ne changera rien.
    _setup(tmp_path, monkeypatch, lambda path, payload: None)
    asyncio.run(backend_client.queue_mission_status(14, "cancelled", payment_status="refunded", refund_amount=10.0))
    asyncio.run(backend_client.queue_payment(5, "paid_escrow", mission_id=15))

    RecordingAsyncClient.status_for = staticmethod(lambda path, payload: 409 if payload.get("mission_id") == 14 else 200)
    assert asyncio.run(backend_client.flush_backend_outbox()) is True
    assert [path for path, _ in RecordingAsyncClient.posts] == ["/api/bot/missions/status", "/api/bot/payments"]
    assert db.count_backend_outbox() == 0


def test_dashboard_shows_db_balance_while_money_moves_are_pending(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch, lambda path, payload: None)
    local_row = {"wallet_balance_usd": 90.0, "wallet_balance_cdf": 0.0}
    backend_entity = {"wallet_balance_usd": 0.0, "wallet_balance_cdf": 0.0}

    assert wallet_balances(backend_entity, local_row) == (0.0, 0.0)

    asyncio.run(backend_client.queue_mission_status(16, "completed", payment_status="released"))
    assert wallet_balances(backend_entity, local_row) == (90.0, 0.0)
