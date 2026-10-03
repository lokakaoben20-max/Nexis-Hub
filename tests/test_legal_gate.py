"""Écran d'acceptation des conditions dans le bot (telegram_bot/legal_gate.py),
contre le vrai backend (CONCEPTION_ACCEPTATIONS.md).

Le filtre ne décide rien : il demande au backend ce qui manque, bloque
l'action tant que quelque chose manque, et bloque aussi quand le backend est
injoignable.
"""

import asyncio
import os
from datetime import timedelta

import pytest

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import db
from messages import get_message
from telegram_bot import admin, legal_gate

USER_ID = 42
ADMIN_ID = 999


class DummyUser:
    def __init__(self, telegram_id):
        self.id = telegram_id


class DummyMessage:
    def __init__(self, telegram_id, text=""):
        self.from_user = DummyUser(telegram_id)
        self.text = text
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))


class DummyCallback:
    def __init__(self, telegram_id, data):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessage(telegram_id)
        self.alerts = []

    async def answer(self, text=None, show_alert=False):
        if text:
            self.alerts.append(text)


class DummyState:
    def __init__(self, data=None):
        self.data = dict(data or {})

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)


async def _french(telegram_id):
    return "fr"


@pytest.fixture(autouse=True)
def _bot(tmp_path, monkeypatch):
    db.DB_PATH = tmp_path / "bot.db"
    db.init_db()
    # Les faux messages tiennent lieu des types aiogram dans le filtre.
    monkeypatch.setattr(legal_gate, "Message", DummyMessage)
    monkeypatch.setattr(legal_gate, "CallbackQuery", DummyCallback)
    monkeypatch.setattr(legal_gate, "get_user_language", _french)
    monkeypatch.setattr(admin, "ADMIN_TELEGRAM_ID", str(ADMIN_ID))
    legal_gate._complete_until.clear()
    yield
    legal_gate._complete_until.clear()


def _publish(live_backend, key, version="v1", effective_in=timedelta(0)):
    from backend.app import ledger, legal

    with live_backend.database.SessionLocal() as session:
        legal.publish_version(session, key, version, f"https://exemple.test/{key}/{version}", b"Texte", ledger._utcnow() + effective_in)
        session.commit()


def _publish_client_documents(live_backend, version="v1", effective_in=timedelta(0)):
    for key in ("conditions_generales", "donnees_transferts"):
        _publish(live_backend, key, version, effective_in)


def _acceptances(live_backend):
    from backend.app import legal

    with live_backend.database.SessionLocal() as session:
        return [(row.decision, row.channel) for row in session.query(legal.LegalAcceptance).order_by(legal.LegalAcceptance.id)]


def _through_gate(event, state=None):
    """Passe l'évènement dans le filtre ; renvoie True si l'action a été exécutée."""
    reached = []

    async def handler(event, data):
        reached.append(event)
        return "handled"

    data = {"event_from_user": event.from_user, "state": state or DummyState()}
    asyncio.run(legal_gate.LegalGateMiddleware()(handler, event, data))
    return bool(reached)


def _buttons(markup):
    return [button for row in markup.inline_keyboard for button in row]


def _click(callback_data, state, telegram_id=USER_ID):
    callback = DummyCallback(telegram_id, callback_data)
    asyncio.run(legal_gate.legal_decision(callback, state))
    return callback


def test_everything_passes_while_nothing_is_published(live_backend):
    assert _through_gate(DummyCallback(USER_ID, "profil_client"))


def test_missing_acceptance_blocks_the_action_and_shows_the_document(live_backend):
    _publish_client_documents(live_backend)
    event = DummyCallback(USER_ID, "client_demande")

    assert not _through_gate(event)

    text, markup = event.message.answers[0]
    assert text == get_message("legal_prompt_conditions_generales", "fr")
    read, accept, refuse = _buttons(markup)
    assert read.url == "https://exemple.test/conditions_generales/v1"
    assert accept.callback_data == "legal:a:cg:v1"
    assert refuse.callback_data == "legal:r:cg:v1"


def test_accepting_chains_the_documents_then_lets_the_person_through(live_backend):
    _publish_client_documents(live_backend)
    state = DummyState()
    assert not _through_gate(DummyCallback(USER_ID, "client_demande"), state)

    first = _click("legal:a:cg:v1", state)
    assert first.message.answers[0][0] == get_message("legal_prompt_donnees_transferts", "fr")
    second = _click("legal:a:dt:v1", state)
    assert second.message.answers[0][0] == get_message("legal_all_accepted", "fr")

    assert _acceptances(live_backend) == [("accepted", "telegram"), ("accepted", "telegram")]
    assert _through_gate(DummyCallback(USER_ID, "client_demande"))


def test_a_future_provider_must_also_accept_the_provider_terms(live_backend):
    _publish_client_documents(live_backend)
    _publish(live_backend, "conditions_prestataires")
    state = DummyState()
    assert not _through_gate(DummyCallback(USER_ID, "profil_prestataire"), state)
    assert state.data["legal_role"] == "provider"

    _click("legal:a:cg:v1", state)
    second = _click("legal:a:dt:v1", state)
    assert second.message.answers[0][0] == get_message("legal_prompt_conditions_prestataires", "fr")
    third = _click("legal:a:cp:v1", state)
    assert third.message.answers[0][0] == get_message("legal_all_accepted", "fr")


def test_refusing_is_recorded_and_keeps_the_action_blocked(live_backend):
    _publish_client_documents(live_backend)
    state = DummyState()

    refused = _click("legal:r:cg:v1", state)

    assert refused.message.answers[0][0] == get_message("legal_refused", "fr")
    assert _acceptances(live_backend) == [("refused", "telegram")]
    assert not _through_gate(DummyCallback(USER_ID, "client_demande"))


def test_an_unreachable_backend_blocks_the_action(monkeypatch):
    # Pas de `live_backend` : la fixture par défaut refuse toute connexion.
    event = DummyMessage(USER_ID, "Bonjour")

    assert not _through_gate(event)
    assert event.answers[0][0] == get_message("legal_backend_unavailable", "fr")


def test_an_unreachable_backend_records_nothing_on_click():
    callback = _click("legal:a:cg:v1", DummyState())
    assert callback.alerts == [get_message("legal_backend_unavailable", "fr")]
    assert callback.message.answers == []


@pytest.mark.parametrize(
    "event",
    [
        DummyMessage(USER_ID, "/start"),
        DummyMessage(USER_ID, "/start parrain42"),
        DummyCallback(USER_ID, "lang_fr"),
        DummyCallback(USER_ID, "legal:a:cg:v1"),
        DummyMessage(ADMIN_ID, "/admin"),
    ],
)
def test_start_language_acceptance_buttons_and_admin_are_not_filtered(event):
    # Backend injoignable : seul un évènement exempté peut passer.
    assert _through_gate(event)


def test_a_complete_status_is_kept_ten_minutes(live_backend, monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(legal_gate.time, "monotonic", lambda: now[0])
    assert _through_gate(DummyCallback(USER_ID, "client_demande"))

    # Une version entre en vigueur : le filtre ne la voit qu'à l'expiration.
    _publish_client_documents(live_backend)
    now[0] += legal_gate.COMPLETE_CACHE_SECONDS - 1
    assert _through_gate(DummyCallback(USER_ID, "client_demande"))
    now[0] += 2
    assert not _through_gate(DummyCallback(USER_ID, "client_demande"))


def test_a_version_replaced_during_reading_shows_the_new_one(live_backend):
    _publish(live_backend, "conditions_generales", "v1", timedelta(days=-30))
    state = DummyState()
    assert not _through_gate(DummyCallback(USER_ID, "client_demande"), state)
    _publish(live_backend, "conditions_generales", "v2", timedelta(seconds=-1))

    callback = _click("legal:a:cg:v1", state)

    assert callback.message.answers[0][0] == get_message("legal_version_changed", "fr")
    text, markup = callback.message.answers[1]
    assert text == get_message("legal_prompt_conditions_generales", "fr")
    assert _buttons(markup)[1].callback_data == "legal:a:cg:v2"
    assert _acceptances(live_backend) == []


def test_a_malformed_button_does_nothing(live_backend):
    callback = _click("legal:a:zz:v1", DummyState())
    assert callback.message.answers == []
    assert _acceptances(live_backend) == []
