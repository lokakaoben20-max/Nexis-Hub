"""Phase 3, groupe admin : extraction vers telegram_bot/admin.py (voir AGENTS.md).

Complète `tests/test_dispute_flow.py` (résolution des litiges) et
`tests/test_provider_verification.py` (vérification/refus) : couvre ici les
handlers pas encore testés ailleurs (suspension/réactivation prestataire,
services proposés, accès admin) et vérifie que les 6 handlers qui utilisaient
encore le `bot` global dans `main.py` (`admin_accept_service`,
`admin_verify_provider`, `admin_reject_provider`, `admin_suspend_provider`,
`admin_unsuspend_provider`, `admin_reject_service`) utilisent bien
`callback.bot` après extraction — même style que
`tests/test_payment_flow_extraction.py` (`DummyBot` capture les envois via
`callback.bot`, pas une instance globale, donc le mock ne fonctionnerait pas
sinon).
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
from telegram_bot import admin, backend_client


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
    """Capture les envois sortants via `callback.bot` (voir docstring du module)."""

    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None
        self.answered_texts = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered_texts.append(text)


class DummyUser:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Admin"


class DummyCallback:
    def __init__(self, telegram_id, data="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessageObject()
        self.bot = bot or DummyBot()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


def _init_db(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()


def _use_dummy_backend(monkeypatch):
    DummyAsyncClient.last_request = None
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


# --- accès admin -------------------------------------------------------------


def test_non_admin_is_refused_on_any_handler(tmp_path, monkeypatch):
    _init_db(tmp_path)
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: False)

    callback = DummyCallback(telegram_id=999, data="admin_stats")
    asyncio.run(admin.admin_stats(callback))

    assert callback.answered == "Accès admin refusé."
    assert callback.message.edited_text is None, "aucune donnée admin ne doit être révélée à un non-admin"


# --- suspension / réactivation prestataire -----------------------------------


def test_admin_suspend_provider_notifies_via_callback_bot_and_syncs_backend(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_provider_language", lambda telegram_id: _async_return("fr"))

    telegram_id = 2001
    db.create_provider(telegram_id, "+243800002001", "A Suspendre", ["service_plomberie"], ["Gombe"], language="fr")
    local_id = db.get_provider_by_telegram_id(telegram_id)["id"]

    bot = DummyBot()
    callback = DummyCallback(999, data=f"admin_suspend_provider_{local_id}", bot=bot)
    asyncio.run(admin.admin_suspend_provider(callback))

    provider = db.get_provider_by_telegram_id(telegram_id)
    assert provider["is_suspended"] == 1
    assert DummyAsyncClient.last_request["url"].endswith(f"/api/bot/providers/{telegram_id}/suspend"), (
        "le sync backend doit cibler telegram_id, pas l'id interne SQLite"
    )
    assert bot.messages, "le prestataire doit être notifié via callback.bot"
    assert bot.messages[0][0] == telegram_id


def test_admin_unsuspend_provider_notifies_via_callback_bot_and_syncs_backend(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_provider_language", lambda telegram_id: _async_return("fr"))

    telegram_id = 2002
    db.create_provider(telegram_id, "+243800002002", "A Reactiver", ["service_plomberie"], ["Gombe"], language="fr")
    local_id = db.get_provider_by_telegram_id(telegram_id)["id"]
    db.set_provider_suspended(local_id, True)

    bot = DummyBot()
    callback = DummyCallback(999, data=f"admin_unsuspend_provider_{local_id}", bot=bot)
    asyncio.run(admin.admin_unsuspend_provider(callback))

    provider = db.get_provider_by_telegram_id(telegram_id)
    assert provider["is_suspended"] == 0
    assert DummyAsyncClient.last_request["url"].endswith(f"/api/bot/providers/{telegram_id}/unsuspend")
    assert bot.messages
    assert bot.messages[0][0] == telegram_id


def test_admin_suspend_provider_answers_alert_when_provider_missing(tmp_path, monkeypatch):
    _init_db(tmp_path)
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)

    callback = DummyCallback(999, data="admin_suspend_provider_9999")
    asyncio.run(admin.admin_suspend_provider(callback))

    assert callback.answered == "Prestataire introuvable."


# --- services proposés --------------------------------------------------------


def test_admin_accept_service_notifies_provider_via_callback_bot(tmp_path, monkeypatch):
    _init_db(tmp_path)
    telegram_id = 2003
    db.create_provider(telegram_id, "+243800002003", "Proposeur", ["service_plomberie"], ["Gombe"], language="fr")
    request_id = db.create_service_request(telegram_id, "Service exotique", "Description suffisamment longue.")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)

    bot = DummyBot()
    callback = DummyCallback(999, data=f"admin_accept_service_{request_id}", bot=bot)
    asyncio.run(admin.admin_accept_service(callback))

    request = db.get_service_request_by_id(request_id)
    assert request["status"] == "accepted"
    assert bot.messages
    assert bot.messages[0][0] == telegram_id, "la notification doit partir vers le prestataire, pas l'admin"


def test_admin_reject_service_notifies_provider_via_callback_bot(tmp_path, monkeypatch):
    _init_db(tmp_path)
    telegram_id = 2004
    db.create_provider(telegram_id, "+243800002004", "Proposeur", ["service_plomberie"], ["Gombe"], language="fr")
    request_id = db.create_service_request(telegram_id, "Service refusé", "Description suffisamment longue.")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)

    bot = DummyBot()
    callback = DummyCallback(999, data=f"admin_reject_service_{request_id}", bot=bot)
    asyncio.run(admin.admin_reject_service(callback))

    request = db.get_service_request_by_id(request_id)
    assert request["status"] == "rejected"
    assert bot.messages
    assert bot.messages[0][0] == telegram_id


def test_admin_service_requests_lists_pending_only(tmp_path, monkeypatch):
    _init_db(tmp_path)
    telegram_id = 2005
    db.create_provider(telegram_id, "+243800002005", "Proposeur", ["service_plomberie"], ["Gombe"], language="fr")
    accepted_id = db.create_service_request(telegram_id, "Déjà traité", "Description suffisamment longue.")
    db.update_service_request_status(accepted_id, "accepted", "note")
    pending_id = db.create_service_request(telegram_id, "En attente", "Description suffisamment longue.")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)

    callback = DummyCallback(999, data="admin_service_requests")
    asyncio.run(admin.admin_service_requests(callback))

    listed_ids = {int(text.split("SRV-")[1][:4]) for text in callback.message.answered_texts if "SRV-" in text}
    assert pending_id in listed_ids
    assert accepted_id not in listed_ids, "une proposition déjà traitée ne doit plus apparaître dans la file"
