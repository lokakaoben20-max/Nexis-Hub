"""Connexion à l'application mobile par le bot Telegram (étape 1, PR 2) :
`/start app_<jeton>`, partage du numéro, code affiché, refus traduits.

Le backend est remplacé par un faux client : ces tests vérifient le bot
(ce qu'il envoie, ce qu'il montre). Les règles elles-mêmes sont testées dans
backend/tests/test_app_auth.py.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from aiogram.filters import CommandObject

import main
from messages import get_message
from telegram_bot import app_login, backend_client

TOKEN = "A" * 32


class Contact:
    def __init__(self, phone_number, user_id):
        self.phone_number = phone_number
        self.user_id = user_id


class User:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Test"


class Message:
    def __init__(self, telegram_id, text=None, contact=None):
        self.from_user = User(telegram_id)
        self.text = text
        self.contact = contact
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append(text)


class State:
    def __init__(self, data=None):
        self._data = dict(data or {})
        self.state = None

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self._data = {}
        self.state = None


async def _lang(telegram_id):
    return "fr"


@pytest.fixture(autouse=True)
def french(monkeypatch):
    monkeypatch.setattr(backend_client, "get_user_language", _lang)


@pytest.fixture
def backend(monkeypatch):
    calls = []
    outcome = {"result": {"status": "ok", "code": "482913", "expires_at": "2026-11-07T08:10:00"}}

    async def fake(telegram_id, start_token, phone):
        calls.append((telegram_id, start_token, phone))
        result = outcome["result"]
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(backend_client, "app_login_telegram_contact", fake)
    return calls, outcome


def start(message, state, args):
    asyncio.run(main.cmd_start(message, state, CommandObject(prefix="/", command="start", args=args)))


def test_start_from_the_app_asks_for_the_shared_number(backend):
    message, state = Message(601, text=f"/start app_{TOKEN}"), State()

    start(message, state, f"app_{TOKEN}")

    assert state.state == app_login.AppLogin.contact
    assert state._data["app_login_token"] == TOKEN
    assert message.answers == [get_message("app_login_share_phone", "fr")]


def test_a_normal_start_still_shows_the_welcome(backend):
    message, state = Message(601, text="/start"), State()

    start(message, state, None)

    assert state.state is None
    assert message.answers == [get_message("welcome", "fr")]


def test_the_shared_own_number_gets_the_code_from_the_backend(backend):
    calls, _ = backend
    state = State({"app_login_token": TOKEN, "language": "fr"})
    message = Message(601, contact=Contact("243810000001", user_id=601))

    asyncio.run(app_login.contact_pour_app(message, state))

    assert calls == [(601, TOKEN, "243810000001")]
    assert message.answers == [get_message("app_login_code", "fr", code="482913")]
    assert state.state is None and "app_login_token" not in state._data


def test_a_typed_number_is_refused_and_nothing_is_asked_to_the_backend(backend):
    calls, _ = backend
    state = State({"app_login_token": TOKEN, "language": "fr"})
    message = Message(601, text="+243810000001")

    asyncio.run(app_login.contact_pour_app(message, state))

    assert calls == []
    assert message.answers == [get_message("phone_required", "fr")]
    assert state._data["app_login_token"] == TOKEN  # la personne peut encore partager son numéro


def test_someone_elses_contact_is_refused(backend):
    calls, _ = backend
    state = State({"app_login_token": TOKEN, "language": "fr"})
    message = Message(601, contact=Contact("+243810000999", user_id=999))

    asyncio.run(app_login.contact_pour_app(message, state))

    assert calls == []
    assert message.answers == [get_message("phone_contact_not_own", "fr")]


@pytest.mark.parametrize(
    "code,key",
    [
        ("link_invalid", "app_login_link_invalid"),
        ("phone_mismatch", "app_login_phone_mismatch"),
        ("invalid_phone", "app_login_phone_mismatch"),
        ("phone_conflict", "app_login_phone_conflict"),
        ("auth_not_configured", "app_login_unavailable"),
    ],
)
def test_backend_refusals_are_explained_and_no_code_is_shown(backend, code, key):
    _, outcome = backend
    outcome["result"] = backend_client.MoneyRefused(code)
    state = State({"app_login_token": TOKEN, "language": "fr"})
    message = Message(601, contact=Contact("+243810000001", user_id=601))

    asyncio.run(app_login.contact_pour_app(message, state))

    assert message.answers == [get_message(key, "fr")]


def test_an_unreachable_backend_shows_no_code(backend):
    _, outcome = backend
    outcome["result"] = backend_client.BackendUnavailable("down")
    state = State({"app_login_token": TOKEN, "language": "fr"})
    message = Message(601, contact=Contact("+243810000001", user_id=601))

    asyncio.run(app_login.contact_pour_app(message, state))

    assert message.answers == [get_message("app_login_unavailable", "fr")]


@pytest.mark.parametrize("lang", ["fr", "ln", "en"])
def test_the_code_message_exists_in_every_language_and_warns(lang):
    text = get_message("app_login_code", lang, code="123456")

    assert "123456" in text and "⚠️" in text
