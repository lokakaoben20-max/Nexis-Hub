"""Phase 3 (pilote) : flow inscription/profil extrait vers telegram_bot/registration.py.

Miroir du style de tests/test_bot_backend_sync.py. Couvre la garantie centrale de ce
pilote : double écriture (backend + db.py) maintenue tant que find_matching_providers
(flow mission) et la Mini App lisent encore db.py — voir V5_MIGRATION_PLAN.md, Phase 3.
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import db
from telegram_bot import backend_client, registration


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyAsyncClient:
    """Capture la dernière requête envoyée, comme dans test_bot_backend_sync.py."""

    last_request = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        DummyAsyncClient.last_request = {"method": "post", "url": url, "json": json}
        return DummyResponse({"status": "ok", "provider": json or {}})

    async def patch(self, url, json=None):
        DummyAsyncClient.last_request = {"method": "patch", "url": url, "json": json}
        return DummyResponse({"status": "ok", "provider": json or {}})

    async def get(self, url, params=None):
        DummyAsyncClient.last_request = {"method": "get", "url": url}
        return DummyResponse({"client": None, "provider": None})


class RaisingAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        raise RuntimeError("backend unreachable")

    async def patch(self, url, json=None):
        raise RuntimeError("backend unreachable")

    async def get(self, url, params=None):
        raise RuntimeError("backend unreachable")


class DummyMessage:
    def __init__(self):
        self.edited_text = None
        self.reply_markup = None

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text
        self.reply_markup = reply_markup

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text
        self.reply_markup = reply_markup


class DummyUser:
    def __init__(self, telegram_id, first_name="Test"):
        self.id = telegram_id
        self.first_name = first_name


class DummyCallback:
    def __init__(self, telegram_id, data=""):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessage()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


class DummyState:
    def __init__(self, data=None):
        self._data = data or {}
        self.cleared = False

    async def get_data(self):
        return self._data

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        self._data["_state"] = state

    async def clear(self):
        self.cleared = True
        self._data = {}


def _use_dummy_backend(monkeypatch, client=DummyAsyncClient):
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", client)
    # get_provider_language/get_user_language lisent fetch_backend_profile en premier ;
    # None force la lecture locale db.py, indépendamment de la forme de DummyAsyncClient.
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


def _init_db(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()


def test_terminer_inscription_prestataire_writes_backend_and_local(monkeypatch, tmp_path):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)

    callback = DummyCallback(telegram_id=501, data="provider_communes_done")
    state = DummyState(data={
        "provider_phone": "+243800000501",
        "provider_full_name": "Alice Prestataire",
        "provider_services": ["service_plomberie"],
        "provider_communes": ["Gombe"],
        "language": "fr",
    })

    asyncio.run(registration.terminer_inscription_prestataire(callback, state))

    local_provider = db.get_provider_by_telegram_id(501)
    assert local_provider is not None
    assert local_provider["full_name"] == "Alice Prestataire"

    assert DummyAsyncClient.last_request["method"] == "post"
    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/providers")
    assert DummyAsyncClient.last_request["json"]["telegram_id"] == 501
    assert state.cleared is True


def test_changer_disponibilite_writes_backend_and_local(monkeypatch, tmp_path):
    _init_db(tmp_path)
    db.create_provider(502, "+243800000502", "Bob Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    _use_dummy_backend(monkeypatch)

    callback = DummyCallback(telegram_id=502, data="provider_status_offline")
    asyncio.run(registration.changer_disponibilite(callback))

    assert db.get_provider_by_telegram_id(502)["status"] == "offline"
    assert DummyAsyncClient.last_request["method"] == "patch"
    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/providers/502/status")
    assert DummyAsyncClient.last_request["json"] == {"status": "offline"}


def test_changer_disponibilite_survives_backend_outage(monkeypatch, tmp_path):
    """L'écriture locale ne doit jamais dépendre du succès de l'appel backend."""
    _init_db(tmp_path)
    db.create_provider(503, "+243800000503", "Carla Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    _use_dummy_backend(monkeypatch, client=RaisingAsyncClient)

    callback = DummyCallback(telegram_id=503, data="provider_status_available")
    asyncio.run(registration.changer_disponibilite(callback))

    assert db.get_provider_by_telegram_id(503)["status"] == "available"


def test_enregistrer_services_modifies_writes_backend_and_local(monkeypatch, tmp_path):
    _init_db(tmp_path)
    db.create_provider(504, "+243800000504", "Dan Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    _use_dummy_backend(monkeypatch)

    callback = DummyCallback(telegram_id=504, data="edit_services_done")
    state = DummyState(data={"provider_services_edit": ["service_electricite", "service_informatique"]})

    asyncio.run(registration.enregistrer_services_modifies(callback, state))

    local_provider = db.get_provider_by_telegram_id(504)
    assert "service_electricite" in local_provider["services"]
    assert DummyAsyncClient.last_request["method"] == "patch"
    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/providers/504/services")
    assert set(DummyAsyncClient.last_request["json"]["services"]) == {"service_electricite", "service_informatique"}
    assert state.cleared is True


def test_langue_fr_updates_both_user_and_provider_language(monkeypatch, tmp_path):
    _init_db(tmp_path)
    db.create_user(505, "+243800000505", "Eve Cliente", language="en")
    _use_dummy_backend(monkeypatch)

    callback = DummyCallback(telegram_id=505, data="lang_fr")
    state = DummyState()

    asyncio.run(registration.langue_fr(callback, state))

    assert db.get_user_by_telegram_id(505)["language"] == "fr"
    # langue_fr synchronise systématiquement client ET prestataire (voir le
    # commentaire dans registration.py) : la dernière requête capturée est
    # celle du prestataire (envoyée en second), mais l'appel côté client a bien
    # eu lieu avant de lever une éventuelle exception (RuntimeError sinon).
    assert DummyAsyncClient.last_request["json"]["language"] == "fr"
