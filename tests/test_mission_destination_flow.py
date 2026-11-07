"""Lieu exact de la mission dans le bot Telegram.

Le client envoie un point (sa position, ou un point choisi par 📎 → Position)
puis écrit un repère ; le prestataire ne lit ce lieu, dans le backend, qu'une
fois la mission payée (« 📍 Voir le lieu »)."""

import asyncio
from types import SimpleNamespace

import db
from messages import get_message
from telegram_bot import keyboards, mission
from tests.test_mission_flow_extraction import (
    DummyBot,
    DummyCallback,
    DummyState,
    _async_return,
    _init_db,
    _mission_request,
)


class LocationBot(DummyBot):
    def __init__(self):
        super().__init__()
        self.locations = []

    async def send_location(self, chat_id, latitude, longitude, **kwargs):
        self.locations.append((chat_id, latitude, longitude))


class ChatMessage:
    """Message reçu du client : texte, ou position Telegram."""

    def __init__(self, telegram_id=900, text=None, location=None):
        self.from_user = SimpleNamespace(id=telegram_id, first_name="Ada <b>")
        self.text = text
        self.location = location
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))


class AnsweringMessageObject:
    """`callback.message` qui garde les messages envoyés en réponse."""

    def __init__(self):
        self.edited_text = None
        self.answers = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))


def _point(latitude=-4.3076, longitude=15.3125):
    return SimpleNamespace(latitude=latitude, longitude=longitude, live_period=None)


def _location_button(markup):
    return markup.keyboard[0][0]


def test_choosing_the_commune_asks_for_the_exact_place():
    state = DummyState(data={"language": "fr", "service": "service_plomberie"})
    callback = DummyCallback(900, data="commune_gombe")
    callback.message = AnsweringMessageObject()

    asyncio.run(mission.commune_selectionnee(callback, state))

    assert state._data["commune"] == "Gombe"
    assert state._data["_state"] == mission.MissionRequest.location
    text, markup = callback.message.answers[-1]
    assert text == get_message("ask_mission_location", "fr")
    assert _location_button(markup).request_location is True
    assert _location_button(markup).text == get_message("button_send_location", "fr")


def test_a_text_is_not_a_place():
    state = DummyState(data={"language": "fr", "_state": mission.MissionRequest.location})
    message = ChatMessage(text="Gombe, avenue du commerce")

    asyncio.run(mission.position_recue(message, state))

    assert message.answers[-1][0] == get_message("location_required", "fr")
    assert "destination_latitude" not in state._data
    assert state._data["_state"] == mission.MissionRequest.location


def test_the_point_then_the_landmark_are_kept_and_the_currency_comes_next():
    state = DummyState(data={"language": "fr"})

    point_message = ChatMessage(location=_point())
    asyncio.run(mission.position_recue(point_message, state))
    assert (state._data["destination_latitude"], state._data["destination_longitude"]) == (-4.3076, 15.3125)
    assert state._data["_state"] == mission.MissionRequest.landmark
    assert point_message.answers[-1][0] == get_message("ask_mission_landmark", "fr")
    assert point_message.answers[-1][1].remove_keyboard is True

    too_short = ChatMessage(text=" a ")
    asyncio.run(mission.repere_recu(too_short, state))
    assert too_short.answers[-1][0] == get_message("landmark_invalid", "fr")
    assert "destination_landmark" not in state._data

    landmark = ChatMessage(text="  Portail   bleu après la poste ")
    asyncio.run(mission.repere_recu(landmark, state))
    assert state._data["destination_landmark"] == "Portail bleu après la poste"
    assert state._data["_state"] is None
    assert landmark.answers[-1][0] == get_message("choose_currency", "fr")


def test_the_request_can_be_cancelled_at_the_place_step():
    state = DummyState(data={"language": "fr", "service": "service_plomberie"})
    message = ChatMessage(text=get_message("button_cancel_request", "fr"))

    asyncio.run(mission.position_recue(message, state))

    assert state.cleared is True
    assert message.answers[0][0] == get_message("request_cancelled", "fr")
    assert message.answers[0][1].remove_keyboard is True
    assert "Ada &lt;b&gt;" in message.answers[1][0], "le prénom est échappé"


def test_the_summary_shows_the_landmark_escaped():
    recap = mission.format_recap(_mission_request(destination_landmark="Chez <Mama> & fils"))
    assert "Repère : <b>Chez &lt;Mama&gt; &amp; fils</b>" in recap


def test_a_point_outside_kinshasa_is_asked_again_without_losing_the_request(monkeypatch, tmp_path, live_backend):
    _init_db(tmp_path)
    db.create_user(900, "+243800000900", "Cliente", language="fr")
    db.create_provider(901, "+243800000901", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))
    state = DummyState(data=_mission_request(destination_latitude=0.0, destination_longitude=0.0))

    bot = DummyBot()
    refused = DummyCallback(900, data="mission_confirmer", bot=bot)
    refused.message = AnsweringMessageObject()
    asyncio.run(mission.mission_confirmer(refused, state))

    from backend.app.models import BotMission

    with live_backend.database.SessionLocal() as session:
        assert session.query(BotMission).count() == 0
    assert bot.messages == [], "aucun prestataire prévenu"
    assert refused.message.answers[-1][0].startswith(get_message("destination_outside_service_area", "fr"))
    assert state._data["_state"] == mission.MissionRequest.location
    assert state._data["description"] == "Fuite d'eau", "le reste de la demande est gardé"

    asyncio.run(mission.position_recue(ChatMessage(location=_point()), state))
    landmark = ChatMessage(text="Portail bleu après la poste")
    asyncio.run(mission.repere_recu(landmark, state))
    assert landmark.answers[-1][0] == mission.format_recap(state._data), "retour direct au récapitulatif"

    confirmed = DummyCallback(900, data="mission_confirmer", bot=bot)
    asyncio.run(mission.mission_confirmer(confirmed, state))
    with live_backend.database.SessionLocal() as session:
        created = session.query(BotMission).one()
        assert (created.destination_latitude, created.destination_longitude) == (-4.3076, 15.3125)
    assert [message.chat_id for message in bot.messages] == [901]
    assert "15.3125" not in bot.messages[0].text, "l'alerte ne contient jamais le lieu exact"


def test_the_provider_reads_the_place_only_once_the_mission_is_paid(monkeypatch, live_backend):
    from backend.app import ledger

    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))
    mission_id, quote_id = live_backend.accepted_quote(900, 901)

    early = DummyCallback(901, data=f"mission_place_{mission_id}", bot=LocationBot())
    asyncio.run(mission.voir_lieu_mission(early))
    assert early.answered == get_message("place_not_available", "fr")
    assert early.bot.locations == []

    live_backend.credit_wallet(900, 100.0)
    with live_backend.database.SessionLocal() as session:
        ledger.fund_mission(
            session, mission_id, method="wallet",
            client_account_id=ledger.account_id_for(session, ledger.TELEGRAM, 900), quote_id=quote_id,
        )

    paid = DummyCallback(901, data=f"mission_place_{mission_id}", bot=LocationBot())
    asyncio.run(mission.voir_lieu_mission(paid))
    assert paid.bot.locations == [(901, -4.3076, 15.3125)]
    assert "Portail bleu après la poste" in paid.bot.messages[-1].text
    assert f"NXH-{mission_id:04d}" in paid.bot.messages[-1].text

    stranger = DummyCallback(555, data=f"mission_place_{mission_id}", bot=LocationBot())
    asyncio.run(mission.voir_lieu_mission(stranger))
    assert stranger.bot.locations == []


def test_the_place_button_says_so_when_the_backend_is_down(monkeypatch):
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))
    callback = DummyCallback(901, data="mission_place_12", bot=LocationBot())

    asyncio.run(mission.voir_lieu_mission(callback))

    assert callback.answered == get_message("service_unavailable", "fr")
    assert callback.bot.locations == []


def test_the_paid_provider_keyboards_offer_the_place():
    for action in ("start", "finish"):
        markup = keyboards.clavier_mission_prestataire(12, action, "fr")
        callbacks = [button.callback_data for row in markup.inline_keyboard for button in row]
        assert "mission_place_12" in callbacks


def test_the_mobile_money_paid_notice_offers_the_place(monkeypatch):
    """Le backend prévient le prestataire d'un paiement Mobile Money : la
    notification propose « Voir le lieu », sans jamais contenir le lieu."""
    from backend.app import tasks

    sent = []
    monkeypatch.setattr(tasks, "send_telegram_message", lambda chat_id, text, reply_markup=None: sent.append((text, reply_markup)))
    monkeypatch.setattr(tasks, "_language", lambda db, telegram_id: "fr")
    intent = SimpleNamespace(mission_id=12, currency="USD")

    tasks._notify_provider_paid(None, 901, intent, {"total": 100, "commission": 10, "net": 90})

    text, markup = sent[0]
    callbacks = [button["callback_data"] for row in markup["inline_keyboard"] for button in row]
    assert callbacks == ["mission_start_12", "mission_place_12"]
