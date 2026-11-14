"""Arrivée du prestataire dans le bot Telegram, contre le vrai backend.

Le prestataire signale « Je suis arrivé » : rien ne démarre, le backend pose
la question au client (avec son code de présence). Le client répond « Oui, il
est là », ou le prestataire tape le code que le client lui donne : la mission
démarre. « Ce n'est pas lui » gèle la mission, après confirmation."""

import asyncio

from messages import get_message
from telegram_bot import payment
from tests.test_dispute_flow import (
    CLIENT_ID,
    PROVIDER_ID,
    DummyCallback,
    DummyMessage,
    DummyState,
    _go_offline,
    _paid_mission,
)


class QuestionMessage:
    """Message du bot qui porte des boutons (question au client)."""

    def __init__(self):
        self.edited_text = None
        self.edited_markup = None
        self.markup_changes = []
        self.answers = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text
        self.edited_markup = reply_markup

    async def edit_reply_markup(self, reply_markup=None):
        self.markup_changes.append(reply_markup)

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))


class CodeMessage(DummyMessage):
    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append(text)
        self.markup = reply_markup


def _tap(handler, telegram_id, data):
    callback = DummyCallback(telegram_id, data=data)
    callback.message = QuestionMessage()
    asyncio.run(handler(callback))
    return callback


def _callbacks(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _code(mission_id):
    from backend.app import presence

    return presence.presence_code(mission_id)


def _type_code(state, text):
    message = CodeMessage(PROVIDER_ID, text=text)
    asyncio.run(payment.prestataire_tape_code(message, state))
    return message


def test_arrival_then_the_client_yes_starts_the_mission(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    live_backend.sent.clear()

    arrived = _tap(payment.prestataire_arrive, PROVIDER_ID, f"presence_arrived_{mission_id}")

    assert live_backend.mission(mission_id).status == "confirmed", "« Je suis arrivé » seul ne démarre rien"
    assert arrived.message.edited_text == get_message("presence_declared_provider", "fr", mission_id=mission_id)
    assert f"presence_code_{mission_id}" in _callbacks(arrived.message.edited_markup)
    [(client_id, question)] = live_backend.sent
    assert client_id == CLIENT_ID and _code(mission_id) in question
    assert [button["callback_data"] for row in live_backend.markups[0][1]["inline_keyboard"] for button in row] == [
        f"presence_yes_{mission_id}", f"presence_notyet_{mission_id}", f"presence_wrong_{mission_id}"
    ]

    yes = _tap(payment.client_confirme_presence, CLIENT_ID, f"presence_yes_{mission_id}")

    assert live_backend.mission(mission_id).status == "in_progress"
    assert yes.message.markup_changes == [None], "les boutons de la question disparaissent"
    assert yes.message.answers[0][0] == get_message("presence_confirmed_client", "fr", mission_id=mission_id)
    assert live_backend.sent[-1] == (PROVIDER_ID, get_message("presence_confirmed_provider", "fr", mission_id=mission_id))


def test_a_second_arrival_tap_soon_after_does_not_ask_again(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    live_backend.sent.clear()

    _tap(payment.prestataire_arrive, PROVIDER_ID, f"presence_arrived_{mission_id}")
    again = _tap(payment.prestataire_arrive, PROVIDER_ID, f"presence_arrived_{mission_id}")

    assert again.message.edited_text == get_message("presence_already_asked_provider", "fr", mission_id=mission_id)
    assert len(live_backend.sent) == 1


def test_an_old_start_button_only_declares_the_arrival(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    live_backend.sent.clear()

    _tap(payment.prestataire_arrive, PROVIDER_ID, f"mission_start_{mission_id}")

    assert live_backend.mission(mission_id).status == "confirmed"
    assert [chat_id for chat_id, _ in live_backend.sent] == [CLIENT_ID]


def test_the_provider_types_the_client_code(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    live_backend.sent.clear()
    state = DummyState()
    asked = DummyCallback(PROVIDER_ID, data=f"presence_code_{mission_id}")
    asyncio.run(payment.prestataire_demande_saisie_code(asked, state))
    assert state.state == payment.PresenceFlow.code
    assert asked.message.edited_text == get_message("presence_ask_code", "fr", mission_id=mission_id)

    not_a_code = _type_code(state, "48 21 ")
    assert not_a_code.answers == [get_message("presence_code_invalid_format", "fr")]
    wrong = _type_code(state, "0000" if _code(mission_id) != "0000" else "1111")
    assert wrong.answers == [get_message("presence_code_wrong", "fr", attempts_left=4)], "le texte mal formé n'est pas compté"
    assert not state.cleared and live_backend.mission(mission_id).status == "confirmed"

    right = _type_code(state, _code(mission_id))

    assert state.cleared
    assert right.answers == [get_message("presence_confirmed_provider", "fr", mission_id=mission_id)]
    assert f"mission_finish_{mission_id}" in _callbacks(right.markup)
    assert live_backend.mission(mission_id).status == "in_progress"
    assert live_backend.sent == [(CLIENT_ID, get_message("presence_confirmed_client", "fr", mission_id=mission_id))]


def test_five_wrong_codes_end_the_code_entry(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    state = DummyState({"presence_mission_id": mission_id})
    wrong = "0000" if _code(mission_id) != "0000" else "1111"

    answers = [_type_code(state, wrong).answers[0] for _ in range(5)]

    assert answers[3] == get_message("presence_code_wrong", "fr", attempts_left=1)
    assert answers[4] == get_message("presence_code_locked", "fr")
    assert state.cleared
    assert live_backend.mission(mission_id).status == "confirmed"


def test_not_yet_keeps_the_buttons_and_warns_the_provider(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    _tap(payment.prestataire_arrive, PROVIDER_ID, f"presence_arrived_{mission_id}")
    live_backend.sent.clear()

    not_yet = _tap(payment.client_presence_pas_encore, CLIENT_ID, f"presence_notyet_{mission_id}")

    assert not_yet.answered == get_message("presence_not_yet_client", "fr")
    assert not_yet.message.markup_changes == [], "le client pourra encore répondre « oui »"
    assert live_backend.sent == [(PROVIDER_ID, get_message("presence_not_yet_provider", "fr", mission_id=mission_id))]
    assert live_backend.mission(mission_id).status == "confirmed"


def test_that_is_not_him_asks_to_confirm_then_freezes_the_mission(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)

    first = _tap(payment.client_presence_pas_lui, CLIENT_ID, f"presence_wrong_{mission_id}")
    assert first.answered == get_message("presence_wrong_confirm_prompt", "fr")
    assert _callbacks(first.message.markup_changes[0]) == [f"presence_wrongok_{mission_id}", f"presence_back_{mission_id}"]
    assert live_backend.mission(mission_id).status == "confirmed", "un seul appui ne gèle rien"

    back = _tap(payment.client_presence_retour, CLIENT_ID, f"presence_back_{mission_id}")
    assert _callbacks(back.message.markup_changes[0]) == [
        f"presence_yes_{mission_id}", f"presence_notyet_{mission_id}", f"presence_wrong_{mission_id}"
    ]

    confirmed = _tap(payment.client_presence_pas_lui_confirme, CLIENT_ID, f"presence_wrongok_{mission_id}")

    assert live_backend.mission(mission_id).status == "disputed"
    assert confirmed.message.answers[0][0] == get_message("presence_wrong_client", "fr", mission_id=mission_id)
    assert mission_id in live_backend.disputed_ids()


def test_the_arrival_says_so_when_the_backend_is_down(monkeypatch, live_backend):
    mission_id = _paid_mission(live_backend)
    _go_offline(monkeypatch)

    arrived = _tap(payment.prestataire_arrive, PROVIDER_ID, f"presence_arrived_{mission_id}")
    yes = _tap(payment.client_confirme_presence, CLIENT_ID, f"presence_yes_{mission_id}")

    assert arrived.answered == get_message("money_backend_unavailable", "fr")
    assert yes.answered == get_message("money_backend_unavailable", "fr")
    assert yes.message.markup_changes == []
    assert live_backend.mission(mission_id).status == "confirmed"
