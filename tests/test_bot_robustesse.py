"""Corrections après le test réel du bot du 2026-10-06.

- étapes en cours gardées dans Redis (un redémarrage ne les efface plus) ;
- réponse aux messages et boutons qu'aucun handler ne prend (avant : silence) ;
- « Partager mon numéro » obligatoire, et seulement pour son propre numéro ;
- textes de l'inscription prestataire traduits (erreur de nom, notification admin) ;
- langue gardée par le compte au backend, ou pour l'inscription à venir.
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

from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.redis import RedisStorage

from messages import get_message
from telegram_bot import backend_client, fallback, fsm_storage, registration


class RecordingAsyncClient:
    requests = []

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        RecordingAsyncClient.requests.append(("post", url, json))
        return _Response({"status": "ok"})

    async def patch(self, url, json=None):
        RecordingAsyncClient.requests.append(("patch", url, json))
        return _Response({"status": "ok"})

    async def get(self, url, params=None):
        RecordingAsyncClient.requests.append(("get", url, None))
        return _Response({"client": None, "provider": None})


class _Response:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class Contact:
    def __init__(self, phone_number, user_id):
        self.phone_number = phone_number
        self.user_id = user_id


class User:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Test"


class Chat:
    type = "private"


class Message:
    def __init__(self, telegram_id, text=None, contact=None):
        self.from_user = User(telegram_id)
        self.chat = Chat()
        self.text = text
        self.contact = contact
        self.photo = None
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))


class Callback:
    def __init__(self, telegram_id, data="", bot=None):
        self.from_user = User(telegram_id)
        self.data = data
        self.message = Message(telegram_id)
        self.bot = bot
        self.answered = None
        self.show_alert = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text
        self.show_alert = show_alert


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


class RecordingBot:
    def __init__(self):
        self.sent = []

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        self.sent.append(("message", chat_id, text))

    async def send_photo(self, chat_id, photo, caption=None):
        self.sent.append(("photo", chat_id, caption))


# --- « Partager mon numéro » obligatoire ------------------------------------


def test_provider_typed_phone_number_is_refused():
    state = State({"language": "fr"})
    message = Message(601, text="+243810000601")

    asyncio.run(registration.enregistrer_tel_prestataire(message, state))

    assert state.state is None, "aucune étape suivante sans numéro partagé"
    assert "provider_phone" not in state._data
    assert message.answers[-1][0] == get_message("phone_required", "fr")


def test_provider_cannot_share_someone_elses_contact():
    state = State({"language": "en"})
    message = Message(602, contact=Contact("+243810000999", user_id=999))

    asyncio.run(registration.enregistrer_tel_prestataire(message, state))

    assert state.state is None
    assert "provider_phone" not in state._data
    assert message.answers[-1][0] == get_message("phone_contact_not_own", "en")


def test_provider_contact_without_user_id_is_refused():
    """Une fiche contact sans compte Telegram (user_id absent) ne prouve rien."""
    state = State({"language": "fr"})
    message = Message(605, contact=Contact("+243810000605", user_id=None))

    asyncio.run(registration.enregistrer_tel_prestataire(message, state))

    assert "provider_phone" not in state._data


def test_provider_own_shared_number_is_accepted():
    state = State({"language": "fr"})
    message = Message(603, contact=Contact("+243810000603", user_id=603))

    asyncio.run(registration.enregistrer_tel_prestataire(message, state))

    assert state._data["provider_phone"] == "+243810000603"
    assert state.state == registration.ProviderRegistration.full_name


def test_client_typed_phone_number_creates_no_account(live_backend):
    state = State({"language": "ln"})
    message = Message(604, text="0810000604")

    asyncio.run(registration.enregistrer_client(message, state))

    assert live_backend.profile(604)["client"] is None
    assert message.answers[-1][0] == get_message("phone_required", "ln")


def test_client_own_shared_number_creates_account(live_backend):
    state = State({"language": "fr"})
    message = Message(606, contact=Contact("+243810000606", user_id=606))

    asyncio.run(registration.enregistrer_client(message, state))

    assert live_backend.profile(606)["client"]["phone_number"] == "+243810000606"


# --- Textes traduits ---------------------------------------------------------


def test_invalid_provider_name_error_follows_language():
    state = State({"language": "en"})
    message = Message(610, text="A")

    asyncio.run(registration.enregistrer_nom_prestataire(message, state))

    assert message.answers[-1][0] == get_message("provider_full_name_invalid", "en")
    assert state.state is None


PROVIDER = {
    "account_id": 42,
    "full_name": "Alice <Plombier>",
    "phone_number": "+243810000611",
    "services": ["service_plomberie"],
    "communes": ["Gombe"],
}


def test_new_provider_admin_notification_uses_admin_language(live_backend):
    live_backend.client(700, first_name="Admin", language="en")
    live_backend.grant_admin(700)
    bot = RecordingBot()

    asyncio.run(registration._notifier_admin_nouveau_prestataire(Callback(611, bot=bot), PROVIDER, "id_doc", "selfie", ["p1"]))

    summary = bot.sent[0][2]
    assert summary.startswith("🆕 <b>New provider awaiting approval</b>")
    assert "Alice &lt;Plombier&gt;" in summary, "le nom reste échappé"
    assert [entry[2] for entry in bot.sent[1:4]] == [
        get_message("admin_new_provider_id_caption", "en"),
        get_message("admin_new_provider_selfie_caption", "en"),
        get_message("admin_new_provider_portfolio_caption", "en"),
    ]
    assert bot.sent[-1][2] == get_message("admin_new_provider_approve_prompt", "en")


class FailingFirstBot(RecordingBot):
    """Telegram refuse tout envoi au premier admin (bot bloqué, par exemple)."""

    def __init__(self, blocked):
        super().__init__()
        self.blocked = blocked

    async def send_message(self, chat_id, text, parse_mode=None, reply_markup=None):
        if chat_id == self.blocked:
            raise RuntimeError("Forbidden: bot was blocked by the user")
        await super().send_message(chat_id, text, parse_mode, reply_markup)


def test_new_provider_reaches_every_admin_even_if_one_send_fails(live_backend):
    live_backend.grant_admin(701)
    live_backend.grant_admin(702)
    bot = FailingFirstBot(blocked=701)

    asyncio.run(registration._notifier_admin_nouveau_prestataire(Callback(612, bot=bot), PROVIDER, "id_doc", "selfie", []))

    assert {chat_id for _, chat_id, _ in bot.sent} == {702}
    assert bot.sent[-1][2] == get_message("admin_new_provider_approve_prompt", "fr")


class _UnreachableBackend(RecordingAsyncClient):
    async def get(self, url, params=None):
        raise backend_client.httpx.ConnectError("backend injoignable")


def test_without_backend_answer_no_admin_is_notified():
    bot = RecordingBot()

    asyncio.run(registration._notifier_admin_nouveau_prestataire(Callback(613, bot=bot), PROVIDER, "id_doc", "selfie", []))

    assert bot.sent == []


# --- Langue : celle du compte, gardée pour l'inscription sinon ---------------


def test_language_choice_before_registration_creates_no_profile(live_backend):
    state = State()

    asyncio.run(registration.langue_ln(Callback(620, data="lang_ln"), state))

    assert state._data["language"] == "ln", "gardée pour l'inscription"
    assert live_backend.profile(620)["profile_type"] == "guest"


def test_language_choice_updates_an_existing_client(live_backend):
    live_backend.client(621, first_name="Eve", language="fr")

    asyncio.run(registration.langue_en(Callback(621, data="lang_en"), State()))

    assert live_backend.profile(621)["language"] == "en"


# --- Messages et boutons sans handler ----------------------------------------


def test_unexpected_message_gets_an_answer_in_user_language(live_backend):
    live_backend.client(630, first_name="Eve", language="ln")
    message = Message(630, text="bonjour")

    asyncio.run(fallback.message_inattendu(message))

    assert message.answers == [(get_message("unexpected_message", "ln"), None)]


def test_inactive_button_gets_an_alert():
    callback = Callback(631, data="provider_service_service_plomberie")

    asyncio.run(fallback.bouton_inactif(callback))

    assert callback.answered == get_message("inactive_button", "fr")
    assert callback.show_alert is True


def test_fallback_router_is_included_last():
    import main

    assert main.dp.sub_routers[-1] is fallback.router


def test_fallback_answers_private_chats_only():
    """Dans un groupe, répondre à chaque message serait du bruit."""
    handler = fallback.router.message.handlers[0]
    private = Message(632, text="x")
    group = Message(632, text="x")
    group.chat = type("GroupChat", (), {"type": "group"})()

    assert asyncio.run(handler.check(private))[0] is True
    assert asyncio.run(handler.check(group))[0] is False


# --- Étapes en cours dans Redis ----------------------------------------------


def test_bot_keeps_steps_in_redis_with_expiry():
    import main

    storage = main.dp.storage
    assert isinstance(storage, RedisStorage)
    assert storage.state_ttl == fsm_storage.FSM_TTL
    assert storage.data_ttl == fsm_storage.FSM_TTL
    assert storage.key_builder.prefix == "nexis_fsm"


def test_bot_refuses_to_start_without_redis():
    storage = fsm_storage.build_fsm_storage("redis://127.0.0.1:1/0")
    try:
        with pytest.raises(RuntimeError, match="Redis injoignable"):
            asyncio.run(fsm_storage.ensure_fsm_storage_ready(storage))
    finally:
        asyncio.run(storage.close())


def test_steps_survive_a_restart_when_redis_is_available():
    """Deux stockages distincts sur le même Redis = un redémarrage du bot.
    Ignoré si aucun Redis local ne répond (lancer `docker compose up -d redis`)."""
    url = os.getenv("REDIS_URL", fsm_storage.DEFAULT_REDIS_URL)
    key = StorageKey(bot_id=1, chat_id=987654321, user_id=987654321)

    async def scenario():
        before = fsm_storage.build_fsm_storage(url)
        try:
            await fsm_storage.ensure_fsm_storage_ready(before)
        except RuntimeError:
            await before.close()
            pytest.skip("Redis local injoignable")
        await before.set_state(key, "ProviderRegistration:id_document")
        await before.set_data(key, {"provider_phone": "+243810000640", "provider_services": ["service_plomberie"]})
        await before.close()

        after = fsm_storage.build_fsm_storage(url)
        try:
            return await after.get_state(key), await after.get_data(key)
        finally:
            await after.set_state(key, None)
            await after.set_data(key, {})
            await after.close()

    state, data = asyncio.run(scenario())
    assert state == "ProviderRegistration:id_document"
    assert data["provider_phone"] == "+243810000640"


# --- Qui est admin : seul le backend le dit ----------------------------------


class _AdminAnswer(RecordingAsyncClient):
    status_code = 200
    payload = None

    async def get(self, url, params=None):
        response = _Response(self.payload)
        response.status_code = self.status_code
        return response


@pytest.mark.parametrize(
    "status_code, payload, expected",
    [
        (200, {"status": "ok", "admin": True}, True),
        (200, {"status": "ok", "admin": False}, False),
        (200, {"status": "ok", "admin": "oui"}, None),
        (200, {"status": "ok"}, None),
        (403, {"detail": {"code": "channel_forbidden"}}, None),
        (500, {"admin": True}, None),
    ],
)
def test_admin_status_trusts_only_a_clear_backend_answer(monkeypatch, status_code, payload, expected):
    answer = type("Answer", (_AdminAnswer,), {"status_code": status_code, "payload": payload})
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", answer)
    assert asyncio.run(backend_client.admin_status(999)) is expected


def test_admin_status_is_unknown_when_the_backend_is_unreachable(monkeypatch):
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", _UnreachableBackend)
    assert asyncio.run(backend_client.admin_status(999)) is None
