"""Phase 3, second flow : mission/devis extrait vers telegram_bot/mission.py.

Profils, missions et devis vivent dans le seul backend (fixture `live_backend`),
qui choisit les prestataires prévenus. Verrouille aussi le bug i18n
corrigé pendant l'extraction : l'alerte envoyée aux prestataires matchés était figée
en français (`get_message("new_mission_alert", "fr", ...)`), donc un prestataire
lingala ou anglophone la recevait dans la mauvaise langue.
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from messages import get_message
from telegram_bot import mission


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
        DummyAsyncClient.last_request = {"url": url, "json": json}
        if url.endswith("/api/bot/quotes"):
            return DummyResponse({"status": "ok", "quote": {"id": 777}})
        return DummyResponse({"status": "ok"})

    async def patch(self, url, json=None):
        DummyAsyncClient.last_request = {"url": url, "json": json}
        return DummyResponse({"status": "ok"})

    async def get(self, url, params=None):
        return DummyResponse({"client": None, "provider": None})


class SentMessage:
    def __init__(self, chat_id, text, **kwargs):
        self.chat_id = chat_id
        self.text = text
        self.kwargs = kwargs


class DummyBot:
    """Capture les envois sortants — remplace l'instance aiogram réelle.

    Les handlers extraits utilisent `callback.bot` / `message.bot` plutôt qu'une
    variable globale `bot` : c'est ce qui rend ce mock possible sans monkeypatch
    d'un module tiers.
    """

    def __init__(self):
        self.messages = []
        self.photos = []
        self.voices = []
        self.video_notes = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(SentMessage(chat_id, text, **kwargs))

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.photos.append(SentMessage(chat_id, caption))

    async def send_voice(self, chat_id, voice, caption=None, **kwargs):
        self.voices.append(SentMessage(chat_id, caption))

    async def send_video_note(self, chat_id, video_note, **kwargs):
        self.video_notes.append(SentMessage(chat_id, video_note))
        return SentMessage(chat_id, video_note)


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def edit_reply_markup(self, reply_markup=None):
        self.reply_markup = reply_markup


class DummyUser:
    def __init__(self, telegram_id, first_name="Test"):
        self.id = telegram_id
        self.first_name = first_name


class DummyCallback:
    def __init__(self, telegram_id, data="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessageObject()
        self.bot = bot or DummyBot()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


class DummyMessage:
    def __init__(self, telegram_id, text="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.text = text
        self.voice = None
        self.photo = None
        self.video_note = None
        self.bot = bot or DummyBot()
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append(text)


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


def _mission_request(**fields):
    return {
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Fuite d'eau",
        "urgent": True,
        "language": "fr",
        "creation_key": "demande-test-1",
        "destination_latitude": -4.3076,
        "destination_longitude": 15.3125,
        "destination_landmark": "Portail bleu après la poste",
        **fields,
    }


def test_mission_alert_is_sent_in_each_provider_language(live_backend):
    """Régression : l'alerte était envoyée en français à tous les prestataires."""
    live_backend.client(900, first_name="Cliente")
    live_backend.provider(901, "Prestataire FR", language="fr")
    live_backend.provider(902, "Prestataire EN", language="en")

    bot = DummyBot()
    callback = DummyCallback(telegram_id=900, data="mission_confirmer", bot=bot)
    asyncio.run(mission.mission_confirmer(callback, DummyState(data=_mission_request())))

    sent_by_provider = {m.chat_id: m.text for m in bot.messages}
    assert set(sent_by_provider) == {901, 902}, "les deux prestataires matchés doivent être alertés"
    assert "Nouvelle demande" in sent_by_provider[901]
    assert "New request" in sent_by_provider[902], "le prestataire anglophone recevait l'alerte en français"


def test_confirming_twice_creates_one_mission_and_alerts_the_same_providers(live_backend):
    """Double clic ou réponse perdue : la même clé de création, une seule mission."""
    live_backend.client(900, first_name="Cliente")
    live_backend.provider(901)

    first, second = DummyBot(), DummyBot()
    asyncio.run(mission.mission_confirmer(DummyCallback(900, data="mission_confirmer", bot=first), DummyState(data=_mission_request())))
    # Entre-temps un autre prestataire est devenu disponible : la liste
    # enregistrée avec la mission fait foi.
    live_backend.provider(903, "Nouveau")
    asyncio.run(mission.mission_confirmer(DummyCallback(900, data="mission_confirmer", bot=second), DummyState(data=_mission_request())))

    from backend.app.models import BotMission

    with live_backend.database.SessionLocal() as session:
        assert session.query(BotMission).count() == 1
    assert [m.chat_id for m in first.messages] == [901]
    assert [m.chat_id for m in second.messages] == [901]


def test_the_backend_alerts_the_best_available_providers_only(live_backend):
    """Le backend choisit : trois au plus, les mieux classés, jamais un
    prestataire passé indisponible (dans le bot ou la Mini App), en attente de
    vérification, ou le client lui-même."""
    live_backend.client(900, first_name="Cliente")
    live_backend.provider(900, "Le client aussi prestataire")
    live_backend.provider(941, "Débutant")
    live_backend.provider(942, "Bien noté", average_rating=4.5)
    live_backend.provider(943, "Partenaire", badge="partner")
    live_backend.provider(944, "Expert", badge="expert")
    live_backend.provider(945, "Indisponible", badge="partner", status="offline")
    live_backend.provider(946, "En attente", verified=False)

    bot = DummyBot()
    asyncio.run(mission.mission_confirmer(DummyCallback(900, data="mission_confirmer", bot=bot), DummyState(data=_mission_request())))

    assert live_backend.alerted(1) == [942, 943, 944], "note 4.5 (45 points), puis partenaire (30), puis expert (20)"
    assert sorted(m.chat_id for m in bot.messages) == [942, 943, 944]


def test_mission_is_not_created_while_the_backend_is_down():
    bot = DummyBot()
    callback = DummyCallback(telegram_id=900, data="mission_confirmer", bot=bot)
    state = DummyState(data=_mission_request())
    asyncio.run(mission.mission_confirmer(callback, state))

    assert callback.answered == get_message("service_unavailable", "fr")
    assert bot.messages == [], "aucun prestataire prévenu d'une mission qui n'existe pas"
    assert state._data["creation_key"] == "demande-test-1", "la demande reste à l'écran pour un nouvel essai"


def test_quote_is_recorded_by_the_backend_and_sent_to_the_client(live_backend):
    live_backend.client(910, first_name="Cliente")
    mission_id = live_backend.new_mission(910, alert=(911,), service="service_plomberie")

    bot = DummyBot()
    message = DummyMessage(telegram_id=911, text="Disponible demain", bot=bot)
    state = DummyState(data={
        "quote_mission_id": mission_id,
        "quote_amount": 50.0,
        "quote_currency": "USD",
        "quote_delay_hours": 3,
    })

    asyncio.run(mission.devis_message_recu(message, state))

    from backend.app.models import BotQuote

    with live_backend.database.SessionLocal() as session:
        quote = session.query(BotQuote).one()
    assert (quote.mission_id, quote.provider_telegram_id, quote.amount, quote.status) == (mission_id, 911, 50.0, "pending")
    assert len(bot.messages) == 1, "le client doit recevoir le devis"
    assert bot.messages[0].chat_id == 910
    buttons = [button.callback_data for row in bot.messages[0].kwargs["reply_markup"].inline_keyboard for button in row]
    assert buttons == [f"quote_accept_{quote.id}", f"quote_reject_{quote.id}"]
    assert state.cleared is True


def test_a_provider_who_was_not_alerted_cannot_quote(live_backend):
    live_backend.provider(912, "Pas prévenu", communes=["Limete"])
    mission_id = live_backend.new_mission(910, alert=(911,))

    bot = DummyBot()
    message = DummyMessage(telegram_id=912, text="-", bot=bot)
    state = DummyState(data={"quote_mission_id": mission_id, "quote_amount": 50.0, "quote_currency": "USD", "quote_delay_hours": 3})
    asyncio.run(mission.devis_message_recu(message, state))

    assert message.answers == [get_message("money_error_provider_not_alerted", "fr")]
    assert bot.messages == []
    assert live_backend.mission(mission_id).status == "pending"


def test_the_quote_shows_the_provider_stats_held_by_the_backend(live_backend):
    live_backend.client(930, first_name="Cliente")
    live_backend.provider(931, "Nom Backend", average_rating=4.8, total_missions=12, success_rate=91, badge="partner")
    mission_id = live_backend.new_mission(930, alert=(931,))

    bot = DummyBot()
    message = DummyMessage(telegram_id=931, text="Disponible demain", bot=bot)
    state = DummyState(data={
        "quote_mission_id": mission_id, "quote_amount": 50.0,
        "quote_currency": "USD", "quote_delay_hours": 3,
    })

    asyncio.run(mission.devis_message_recu(message, state))

    sent = bot.messages[0].text
    assert "Nom Backend" in sent
    assert "4.8/5" in sent
    assert "12 missions" in sent
    assert "91% de réussite" in sent


def test_provider_skip_is_counted_by_the_backend_once(live_backend):
    mission_id = live_backend.new_mission(42, alert=(920,))

    for _ in range(2):
        callback = DummyCallback(telegram_id=920, data=f"provider_skip_{mission_id}", bot=DummyBot())
        asyncio.run(mission.passer_mission_prestataire(callback))

    assert live_backend.profile(920)["provider"]["consecutive_ignored"] == 1


def test_provider_skip_says_so_when_the_backend_is_down():
    callback = DummyCallback(telegram_id=920, data="provider_skip_1", bot=DummyBot())
    asyncio.run(mission.passer_mission_prestataire(callback))

    assert callback.answered is not None
    assert callback.message.edited_text is None


class _VideoNote:
    def __init__(self, file_id):
        self.file_id = file_id


def test_a_video_note_is_kept_with_the_mission_and_sent_to_the_providers(live_backend):
    """Note vidéo ronde de Telegram : acceptée comme la note vocale, rangée
    dans le backend avec la mission, et transmise aux prestataires prévenus."""
    live_backend.client(900, first_name="Cliente")
    live_backend.provider(901)

    state = DummyState(data={**_mission_request(), "description_parts": [], "photo_file_ids": [], "voice_file_ids": []})
    message = DummyMessage(telegram_id=900)
    message.video_note = _VideoNote("video-note-1")
    asyncio.run(mission.description_recue(message, state))
    assert message.answers[0].startswith(get_message("media_video_note_added", "fr", count=1))

    bot = DummyBot()
    asyncio.run(mission.mission_confirmer(DummyCallback(900, data="mission_confirmer", bot=bot), state))

    from backend.app.models import MissionMedia

    with live_backend.database.SessionLocal() as session:
        stored = [(media.kind, media.external_id) for media in session.query(MissionMedia).all()]
    assert stored == [("video_note", "video-note-1")]
    assert [(sent.chat_id, sent.text) for sent in bot.video_notes] == [(901, "video-note-1")]
    assert get_message("mission_video_note_caption", "fr", mission_id=1) in [sent.text for sent in bot.messages]


def test_an_unsupported_message_is_still_refused():
    state = DummyState(data={**_mission_request(), "description_parts": [], "photo_file_ids": [], "voice_file_ids": []})
    message = DummyMessage(telegram_id=900)  # ni texte, ni photo, ni note vocale ou vidéo (un autocollant, par exemple)

    asyncio.run(mission.description_recue(message, state))

    assert message.answers == [get_message("media_invalid", "fr")]
