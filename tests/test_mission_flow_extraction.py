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

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(SentMessage(chat_id, text, **kwargs))

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.photos.append(SentMessage(chat_id, caption))

    async def send_voice(self, chat_id, voice, caption=None, **kwargs):
        self.voices.append(SentMessage(chat_id, caption))


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text


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


def test_mission_alert_is_sent_in_each_provider_language(monkeypatch, tmp_path):
    """Régression : l'alerte était envoyée en français à tous les prestataires."""
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(900, "+243800000900", "Cliente", language="fr")
    db.create_provider(901, "+243800000901", "Prestataire FR", ["service_plomberie"], ["Gombe"], language="fr")
    db.create_provider(902, "+243800000902", "Prestataire EN", ["service_plomberie"], ["Gombe"], language="en")

    langs = {901: "fr", 902: "en"}
    monkeypatch.setattr(mission, "get_provider_language", lambda tid: _async_return(langs[tid]))

    bot = DummyBot()
    callback = DummyCallback(telegram_id=900, data="mission_confirmer", bot=bot)
    state = DummyState(data={
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Fuite d'eau",
        "urgent": True,
        "language": "fr",
    })

    asyncio.run(mission.mission_confirmer(callback, state))

    sent_by_provider = {m.chat_id: m.text for m in bot.messages}
    assert set(sent_by_provider) == {901, 902}, "les deux prestataires matchés doivent être alertés"
    assert "Nouvelle demande" in sent_by_provider[901]
    assert "New request" in sent_by_provider[902], "le prestataire anglophone recevait l'alerte en français"


def test_quote_creation_writes_backend_and_local(monkeypatch, tmp_path):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(910, "+243800000910", "Cliente", language="fr")
    db.create_provider(911, "+243800000911", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(910, {
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Fuite",
        "urgent": False,
    })

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

    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/quotes")
    assert DummyAsyncClient.last_request["json"]["amount"] == 50.0

    quotes = db.get_quotes_for_mission(mission_id) if hasattr(db, "get_quotes_for_mission") else None
    if quotes is not None:
        assert len(quotes) == 1, "le devis doit aussi exister en local (double écriture)"

    assert len(bot.messages) == 1, "le client doit recevoir le devis"
    assert bot.messages[0].chat_id == 910
    assert state.cleared is True


def test_devis_message_recu_uses_backend_stats_when_available(monkeypatch, tmp_path):
    """rating côté backend reste toujours 0 (jamais alimenté) : le mapping
    doit lire average_rating, pas rating, pour afficher la vraie note."""
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(930, "+243800000930", "Cliente", language="fr")
    db.create_provider(931, "+243800000931", "Nom Local", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(930, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "Fuite", "urgent": False,
    })

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

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe"))

    assert _ids(chosen) == [504, 503, 502], "le classement backend remplace l'ordre d'inscription"


def test_matching_skips_provider_unavailable_locally(tmp_path, monkeypatch):
    """Passé indisponible via la Mini App (db.py seulement) : jamais alerté,
    même si le backend le classe premier."""
    _matching_db(tmp_path, [511, 512, 513, 514])
    db.update_provider_status(514, "unavailable")
    _backend_ranking(monkeypatch, [514, 513, 512, 511])

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe"))

    assert _ids(chosen) == [513, 512, 511]


def test_matching_keeps_local_provider_unknown_to_backend(tmp_path, monkeypatch):
    _matching_db(tmp_path, [521, 522, 523])
    _backend_ranking(monkeypatch, [523])  # 521/522 jamais synchronisés au backend

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe"))

    assert _ids(chosen) == [523, 521, 522]


def test_matching_falls_back_to_local_order_when_backend_down(tmp_path, monkeypatch):
    _matching_db(tmp_path, [531, 532, 533, 534])
    _backend_ranking(monkeypatch, None)

    chosen = asyncio.run(mission.choose_providers_to_alert("service_plomberie", "Gombe"))

    assert _ids(chosen) == _ids(db.find_matching_providers("service_plomberie", "Gombe"))
