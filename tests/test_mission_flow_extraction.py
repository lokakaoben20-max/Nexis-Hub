"""Phase 3, second flow : mission/devis extrait vers telegram_bot/mission.py.

Couvre la double écriture backend + `db.py` du devis, et verrouille le bug i18n
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

import db
from messages import get_message
from telegram_bot import backend_client, mission


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


def _init_db(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()


def _use_dummy_backend(monkeypatch):
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


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


def test_mission_alert_is_sent_in_each_provider_language(monkeypatch, tmp_path, live_backend):
    """Régression : l'alerte était envoyée en français à tous les prestataires."""
    _init_db(tmp_path)
    db.create_user(900, "+243800000900", "Cliente", language="fr")
    db.create_provider(901, "+243800000901", "Prestataire FR", ["service_plomberie"], ["Gombe"], language="fr")
    db.create_provider(902, "+243800000902", "Prestataire EN", ["service_plomberie"], ["Gombe"], language="en")

    langs = {901: "fr", 902: "en"}
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return(langs[tid]))

    bot = DummyBot()
    callback = DummyCallback(telegram_id=900, data="mission_confirmer", bot=bot)
    asyncio.run(mission.mission_confirmer(callback, DummyState(data=_mission_request())))

    sent_by_provider = {m.chat_id: m.text for m in bot.messages}
    assert set(sent_by_provider) == {901, 902}, "les deux prestataires matchés doivent être alertés"
    assert "Nouvelle demande" in sent_by_provider[901]
    assert "New request" in sent_by_provider[902], "le prestataire anglophone recevait l'alerte en français"


def test_confirming_twice_creates_one_mission_and_alerts_the_same_providers(monkeypatch, tmp_path, live_backend):
    """Double clic ou réponse perdue : la même clé de création, une seule mission."""
    _init_db(tmp_path)
    db.create_user(900, "+243800000900", "Cliente", language="fr")
    db.create_provider(901, "+243800000901", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))

    first, second = DummyBot(), DummyBot()
    asyncio.run(mission.mission_confirmer(DummyCallback(900, data="mission_confirmer", bot=first), DummyState(data=_mission_request())))
    # Entre-temps un autre prestataire est devenu disponible : la liste
    # enregistrée avec la mission fait foi.
    db.create_provider(903, "+243800000903", "Nouveau", ["service_plomberie"], ["Gombe"], language="fr")
    asyncio.run(mission.mission_confirmer(DummyCallback(900, data="mission_confirmer", bot=second), DummyState(data=_mission_request())))

    from backend.app.models import BotMission

    with live_backend.database.SessionLocal() as session:
        assert session.query(BotMission).count() == 1
    assert [m.chat_id for m in first.messages] == [901]
    assert [m.chat_id for m in second.messages] == [901]


def test_mission_is_not_created_while_the_backend_is_down(monkeypatch, tmp_path):
    _init_db(tmp_path)
    db.create_user(900, "+243800000900", "Cliente", language="fr")
    db.create_provider(901, "+243800000901", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    bot = DummyBot()
    callback = DummyCallback(telegram_id=900, data="mission_confirmer", bot=bot)
    state = DummyState(data=_mission_request())
    asyncio.run(mission.mission_confirmer(callback, state))

    assert callback.answered == get_message("service_unavailable", "fr")
    assert bot.messages == [], "aucun prestataire prévenu d'une mission qui n'existe pas"
    assert state._data["creation_key"] == "demande-test-1", "la demande reste à l'écran pour un nouvel essai"


def test_quote_is_recorded_by_the_backend_and_sent_to_the_client(monkeypatch, tmp_path, live_backend):
    _init_db(tmp_path)
    db.create_user(910, "+243800000910", "Cliente", language="fr")
    db.create_provider(911, "+243800000911", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = live_backend.new_mission(910, alert=(911,), service="service_plomberie")

    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(mission, "get_user_language", lambda tid: _async_return("fr"))

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


def test_a_provider_who_was_not_alerted_cannot_quote(monkeypatch, tmp_path, live_backend):
    _init_db(tmp_path)
    db.create_provider(912, "+243800000912", "Pas prévenu", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = live_backend.new_mission(910, alert=(911,))
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))

    bot = DummyBot()
    message = DummyMessage(telegram_id=912, text="-", bot=bot)
    state = DummyState(data={"quote_mission_id": mission_id, "quote_amount": 50.0, "quote_currency": "USD", "quote_delay_hours": 3})
    asyncio.run(mission.devis_message_recu(message, state))

    assert message.answers == [get_message("money_error_provider_not_alerted", "fr")]
    assert bot.messages == []
    assert live_backend.mission(mission_id).status == "pending"


def test_devis_message_recu_uses_backend_stats_when_available(monkeypatch, tmp_path, live_backend):
    """rating côté backend reste toujours 0 (jamais alimenté) : le mapping
    doit lire average_rating, pas rating, pour afficher la vraie note."""
    _init_db(tmp_path)
    db.create_user(930, "+243800000930", "Cliente", language="fr")
    db.create_provider(931, "+243800000931", "Nom Local", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = live_backend.new_mission(930, alert=(931,))

    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(mission, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(mission, "fetch_backend_profile", lambda tid: _async_return({
        "provider": {
            "full_name": "Nom Backend",
            "rating": 0,
            "average_rating": 4.8,
            "total_missions": 12,
            "success_rate": 91,
            "badge": "partner",
            "is_verified": True,
        }
    }))

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


def test_provider_skip_increments_ignored_counter(monkeypatch, tmp_path):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_provider(920, "+243800000920", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))

    callback = DummyCallback(telegram_id=920, data="provider_skip_1", bot=DummyBot())
    asyncio.run(mission.passer_mission_prestataire(callback))

    assert db.get_provider_by_telegram_id(920)["consecutive_ignored"] == 1


# --- matching "mélange" (étape D) : classement backend, disponibilité db.py ---


def _matching_db(tmp_path, provider_ids):
    db.DB_PATH = tmp_path / "test_matching.db"
    db.init_db()
    for telegram_id in provider_ids:
        db.create_provider(telegram_id, f"+2438000{telegram_id}", f"P{telegram_id}", ["service_plomberie"], ["Gombe"], language="fr")
        db.update_provider_status(telegram_id, "available")


def _backend_ranking(monkeypatch, ranking):
    async def fake(telegram_ids):
        return None if ranking is None else [tid for tid in ranking if tid in telegram_ids]
    monkeypatch.setattr(mission, "fetch_backend_provider_ranking", fake)


def _ids(providers):
    return [provider["telegram_id"] for provider in providers]


def test_matching_follows_backend_ranking(tmp_path, monkeypatch):
    _matching_db(tmp_path, [501, 502, 503, 504])
    _backend_ranking(monkeypatch, [504, 503, 502, 501])

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe", 1))

    assert _ids(chosen) == [504, 503, 502], "le classement backend remplace l'ordre d'inscription"


def test_matching_skips_provider_unavailable_locally(tmp_path, monkeypatch):
    """Passé indisponible via la Mini App (db.py seulement) : jamais alerté,
    même si le backend le classe premier."""
    _matching_db(tmp_path, [511, 512, 513, 514])
    db.update_provider_status(514, "unavailable")
    _backend_ranking(monkeypatch, [514, 513, 512, 511])

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe", 1))

    assert _ids(chosen) == [513, 512, 511]


def test_matching_keeps_local_provider_unknown_to_backend(tmp_path, monkeypatch):
    _matching_db(tmp_path, [521, 522, 523])
    _backend_ranking(monkeypatch, [523])  # 521/522 jamais synchronisés au backend

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe", 1))

    assert _ids(chosen) == [523, 521, 522]


def test_matching_falls_back_to_local_order_when_backend_down(tmp_path, monkeypatch):
    _matching_db(tmp_path, [531, 532, 533, 534])
    _backend_ranking(monkeypatch, None)

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe", 1))

    assert _ids(chosen) == _ids(db.find_matching_providers("service_plomberie", "Gombe"))


class _VideoNote:
    def __init__(self, file_id):
        self.file_id = file_id


def test_a_video_note_is_kept_with_the_mission_and_sent_to_the_providers(monkeypatch, tmp_path, live_backend):
    """Note vidéo ronde de Telegram : acceptée comme la note vocale, rangée
    dans le backend avec la mission, et transmise aux prestataires prévenus."""
    _init_db(tmp_path)
    db.create_user(900, "+243800000900", "Cliente", language="fr")
    db.create_provider(901, "+243800000901", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return("fr"))

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


def test_an_unsupported_message_is_still_refused(monkeypatch, tmp_path):
    _init_db(tmp_path)
    state = DummyState(data={**_mission_request(), "description_parts": [], "photo_file_ids": [], "voice_file_ids": []})
    message = DummyMessage(telegram_id=900)  # ni texte, ni photo, ni note vocale ou vidéo (un autocollant, par exemple)

    asyncio.run(mission.description_recue(message, state))

    assert message.answers == [get_message("media_invalid", "fr")]
