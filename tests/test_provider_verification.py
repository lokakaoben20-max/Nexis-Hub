"""Vérification obligatoire des prestataires (V5_MIGRATION_PLAN.md).

Un prestataire ne doit pas être matchable tant qu'un admin n'a pas approuvé sa pièce
d'identité et son selfie. Couvre aussi la régression corrigée au passage :
`admin_verify_provider`/`admin_suspend_provider`/`admin_unsuspend_provider`
envoyaient l'id interne SQLite au backend au lieu du `telegram_id`.
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
from telegram_bot import admin, backend_client, registration


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyAsyncClient:
    last_request = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        DummyAsyncClient.last_request = {"method": "post", "url": url, "json": json}
        return DummyResponse({"status": "ok"})

    async def patch(self, url, json=None):
        DummyAsyncClient.last_request = {"method": "patch", "url": url, "json": json}
        return DummyResponse({"status": "ok"})

    async def get(self, url, params=None):
        return DummyResponse({"client": None, "provider": None})


class DummyBot:
    def __init__(self):
        self.messages = []
        self.photos = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.photos.append((chat_id, caption))


class DummyMessageObject:
    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        pass

    async def answer(self, text, parse_mode=None, reply_markup=None):
        pass


class DummyUser:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Test"


class DummyCallback:
    def __init__(self, telegram_id, data="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessageObject()
        self.bot = bot or DummyBot()

    async def answer(self, text=None, show_alert=False):
        pass


class DummyMessage:
    def __init__(self, telegram_id, photo=True):
        self.from_user = DummyUser(telegram_id)
        self.photo = [type("P", (), {"file_id": f"file_{telegram_id}"})] if photo else None
        self.text = None
        self.voice = None

    async def answer(self, text, parse_mode=None, reply_markup=None):
        pass


class DummyState:
    def __init__(self, data=None):
        self._data = data or {}

    async def get_data(self):
        return self._data

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        pass

    async def clear(self):
        self._data = {}


def _init_db(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()


def _use_dummy_backend(monkeypatch):
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


def test_pending_verification_provider_is_excluded_from_matching(tmp_path):
    _init_db(tmp_path)
    db.create_provider(1001, "+243800001001", "Prestataire En Attente", ["service_plomberie"], ["Gombe"], language="fr")
    db.update_provider_status(1001, "pending_verification")

    matches = db.find_matching_providers("service_plomberie", "Gombe")

    assert all(p["telegram_id"] != 1001 for p in matches), "pending_verification doit rester invisible du matching"


def test_rejected_provider_is_excluded_from_matching(tmp_path):
    _init_db(tmp_path)
    db.create_provider(1002, "+243800001002", "Prestataire Refuse", ["service_plomberie"], ["Gombe"], language="fr")
    db.update_provider_status(1002, "rejected")

    matches = db.find_matching_providers("service_plomberie", "Gombe")

    assert all(p["telegram_id"] != 1002 for p in matches)


def test_full_registration_collects_documents_and_starts_pending(monkeypatch, tmp_path):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)

    telegram_id = 1010
    state = DummyState(data={
        "provider_phone": "+243800001010",
        "provider_full_name": "Nouveau Prestataire",
        "provider_services": ["service_plomberie"],
        "provider_communes": ["Gombe"],
        "language": "fr",
    })

    # communes -> id_document
    asyncio.run(registration.terminer_inscription_prestataire(DummyCallback(telegram_id, "provider_communes_done"), state))

    # id_document photo -> selfie
    asyncio.run(registration.recevoir_document_identite(DummyMessage(telegram_id), state))
    assert state._data["provider_id_document_file_id"] == f"file_{telegram_id}"

    # selfie photo -> portfolio
    asyncio.run(registration.recevoir_selfie(DummyMessage(telegram_id), state))
    assert state._data["provider_selfie_file_id"] == f"file_{telegram_id}"

    # skip portfolio directly -> finalisation
    callback = DummyCallback(telegram_id, "provider_portfolio_done")
    asyncio.run(registration.finaliser_inscription_prestataire(callback, state))

    provider = db.get_provider_by_telegram_id(telegram_id)
    assert provider["status"] == "pending_verification", "ne doit jamais devenir 'available' directement à l'inscription"
    assert provider["id_document_file_id"] == f"file_{telegram_id}"
    assert provider["selfie_file_id"] == f"file_{telegram_id}"

    matches = db.find_matching_providers("service_plomberie", "Gombe")
    assert all(p["telegram_id"] != telegram_id for p in matches)


def test_admin_verify_provider_uses_telegram_id_for_backend_sync(monkeypatch, tmp_path):
    """Régression : le sync backend utilisait l'id interne SQLite, pas telegram_id."""
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    dummy_bot = DummyBot()
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_provider_language", lambda telegram_id: _async_return("fr"))

    telegram_id = 1020
    db.create_provider(telegram_id, "+243800001020", "A Verifier", ["service_plomberie"], ["Gombe"], language="fr")
    db.update_provider_status(telegram_id, "pending_verification")
    local_id = db.get_provider_by_telegram_id(telegram_id)["id"]

    callback = DummyCallback(999, data=f"admin_verify_provider_{local_id}", bot=dummy_bot)
    asyncio.run(admin.admin_verify_provider(callback))

    assert DummyAsyncClient.last_request["url"].endswith(f"/api/bot/providers/{telegram_id}/status"), (
        "le sync backend doit cibler telegram_id, pas l'id interne SQLite"
    )
    provider = db.get_provider_by_telegram_id(telegram_id)
    assert provider["status"] == "available"

    matches = db.find_matching_providers("service_plomberie", "Gombe")
    assert any(p["telegram_id"] == telegram_id for p in matches), "doit redevenir matchable après approbation"
    assert dummy_bot.messages, "le prestataire doit être notifié"


def test_admin_reject_provider_keeps_provider_excluded(monkeypatch, tmp_path):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    dummy_bot = DummyBot()
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_provider_language", lambda telegram_id: _async_return("fr"))

    telegram_id = 1030
    db.create_provider(telegram_id, "+243800001030", "A Refuser", ["service_plomberie"], ["Gombe"], language="fr")
    db.update_provider_status(telegram_id, "pending_verification")
    local_id = db.get_provider_by_telegram_id(telegram_id)["id"]

    callback = DummyCallback(999, data=f"admin_reject_provider_{local_id}", bot=dummy_bot)
    asyncio.run(admin.admin_reject_provider(callback))

    provider = db.get_provider_by_telegram_id(telegram_id)
    assert provider["status"] == "rejected"
    matches = db.find_matching_providers("service_plomberie", "Gombe")
    assert all(p["telegram_id"] != telegram_id for p in matches)
    assert dummy_bot.messages
