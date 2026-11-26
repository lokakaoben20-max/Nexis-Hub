"""Admin du bot : nouveaux services demandés par des prestataires vérifiés
(telegram_bot/admin.py, « Services à valider »).

L'admin voit les photos (lues chez le backend, déchiffrées pour lui seul), la
demande et un éventuel refus précédent ; il approuve ou refuse, avec ou sans
motif. Le prestataire est prévenu une seule fois, dans sa langue.
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

from telegram_bot import admin, backend_client

ADMIN = 999
PROVIDER = 3100
PNG = b"\x89PNG\r\n\x1a\n" + b"\x01" * 64


class Bot:
    def __init__(self, fail: bool = False):
        self.messages = []
        self.fail = fail

    async def send_message(self, chat_id, text, **kwargs):
        if self.fail:
            raise RuntimeError("Telegram injoignable")
        self.messages.append((chat_id, text))


class Chat:
    def __init__(self):
        self.edited_text = None
        self.answered_texts = []
        self.photos = []
        self.albums = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered_texts.append(text)

    async def answer_photo(self, photo, **kwargs):
        self.photos.append(photo.data)

    async def answer_media_group(self, media, **kwargs):
        self.albums.append([item.media.data for item in media])


class User:
    def __init__(self, telegram_id):
        self.id = telegram_id


class Callback:
    def __init__(self, data, bot=None, telegram_id=ADMIN):
        self.from_user = User(telegram_id)
        self.data = data
        self.message = Chat()
        self.bot = bot or Bot()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


class Message:
    def __init__(self, text, bot, telegram_id=ADMIN):
        self.from_user = User(telegram_id)
        self.text = text
        self.bot = bot
        self.answered_texts = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered_texts.append(text)


class State:
    def __init__(self):
        self.state = None
        self.data = {}

    async def set_state(self, state):
        self.state = state

    async def update_data(self, **values):
        self.data.update(values)

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.state, self.data = None, {}


@pytest.fixture
def live(live_backend, tmp_path, monkeypatch):
    monkeypatch.setenv("FILES_DIR", str(tmp_path / "fichiers"))
    live_backend.grant_admin(ADMIN)
    live_backend.provider(PROVIDER, "Patrick Kabongo", language="ln")
    live_backend.sent.clear()
    return live_backend


def _to_provider(live):
    """Messages que le backend a envoyés au prestataire."""
    return [text for chat_id, text in live.sent if chat_id == PROVIDER]


def _ask(service_key="service_nettoyage", photos=(), description="3 ans de nettoyage"):
    async def run():
        ids = [(await backend_client.upload_service_photo(PROVIDER, data))["id"] for data in photos]
        return await backend_client.request_service_addition(PROVIDER, service_key, description, ids)

    return asyncio.run(run())["id"]


def _services(live):
    return live.profile(PROVIDER)["provider"]["services"]


def test_the_admin_sees_the_photos_and_the_request(live):
    other = PNG + b"\x02"
    addition_id = _ask(photos=(PNG, other))
    single_id = _ask("service_jardinage", photos=(PNG,), description="")

    callback = Callback("admin_service_additions")
    asyncio.run(admin.admin_service_additions(callback))

    assert "2 demande(s)" in callback.message.edited_text
    assert callback.message.albums == [[PNG, other]], "photos déchiffrées, dans l'ordre d'envoi"
    assert callback.message.photos == [PNG], "une seule photo : envoyée seule (un album en demande 2)"
    first, second = callback.message.answered_texts
    assert f"AJ-{addition_id:04d}" in first and "Patrick Kabongo" in first and "3 ans de nettoyage" in first
    assert "Photos : <b>2</b>" in first
    assert f"AJ-{single_id:04d}" in second


def test_approval_adds_the_service_and_tells_the_provider_once_in_his_language(live):
    addition_id = _ask()
    bot = Bot()
    first = Callback(f"admin_addition_ok_{addition_id}", bot)
    asyncio.run(admin.admin_answer_addition(first))

    assert "service_nettoyage" in _services(live)
    assert first.message.edited_text.startswith("✅ Approuvé")
    assert bot.messages == [], "le bot ne prévient pas le prestataire lui-même"
    [notice] = _to_provider(live)
    assert notice.startswith("✅ <b>Mosala ya sika endimami</b>")

    again = Callback(f"admin_addition_ok_{addition_id}", bot)
    asyncio.run(admin.admin_answer_addition(again))
    assert again.message.edited_text.startswith("Déjà fait")
    assert len(_to_provider(live)) == 1, "pas de second message au prestataire"

    refuse_after = Callback(f"admin_addition_no_{addition_id}", bot)
    asyncio.run(admin.admin_answer_addition(refuse_after))
    assert "n'attend plus de décision" in refuse_after.message.edited_text
    assert "service_nettoyage" in _services(live)


def test_a_refusal_with_a_reason_reaches_the_provider(live):
    addition_id = _ask()
    bot, state = Bot(), State()
    asyncio.run(admin.admin_addition_ask_reason(Callback(f"admin_addition_why_{addition_id}", bot), state))
    assert state.state == admin.AdminAdditionReason.note

    too_long = Message("x" * 501, bot)
    asyncio.run(admin.admin_addition_reason_received(too_long, state))
    assert state.state is not None and _to_provider(live) == [], "motif trop long : rien n'est décidé"

    answer = Message("Photos <floues>", bot)
    asyncio.run(admin.admin_addition_reason_received(answer, state))
    assert state.state is None
    assert answer.answered_texts[-1].startswith("❌ Refusé")
    assert "service_nettoyage" not in _services(live)
    [notice] = _to_provider(live)
    assert notice.startswith("<b>Bosengi ya mosala etalami</b>")
    assert "Ntina : Photos &lt;floues&gt;" in notice, "motif échappé, dans la langue du prestataire"

    # Nouvelle demande pour le même service : l'admin voit le refus précédent.
    _ask()
    callback = Callback("admin_service_additions")
    asyncio.run(admin.admin_service_additions(callback))
    assert "Déjà refusé une fois : Photos &lt;floues&gt;" in callback.message.answered_texts[0]


def test_a_provider_who_cancelled_cannot_be_approved(live):
    addition_id = _ask()
    asyncio.run(backend_client.cancel_service_addition(PROVIDER, addition_id))
    bot = Bot()
    callback = Callback(f"admin_addition_ok_{addition_id}", bot)
    asyncio.run(admin.admin_answer_addition(callback))
    assert "annulée par le prestataire" in callback.message.edited_text
    assert _to_provider(live) == [] and "service_nettoyage" not in _services(live)


def test_a_non_admin_sees_nothing_and_decides_nothing(live):
    addition_id = _ask(photos=(PNG,))
    listing = Callback("admin_service_additions", telegram_id=PROVIDER)
    asyncio.run(admin.admin_service_additions(listing))
    decision = Callback(f"admin_addition_ok_{addition_id}", telegram_id=PROVIDER)
    asyncio.run(admin.admin_answer_addition(decision))

    assert listing.answered == decision.answered == admin.ACCESS_REFUSED
    assert listing.message.photos == [] and listing.message.edited_text is None
    assert "service_nettoyage" not in _services(live)


def test_the_dashboard_counts_the_services_to_review(live):
    _ask()
    callback = Callback("admin_stats")
    asyncio.run(admin.admin_stats(callback))
    assert "Nouveaux services à valider : <b>1</b>" in callback.message.edited_text


def test_the_decision_never_depends_on_the_bot_reaching_the_provider(live):
    """Le message au prestataire est écrit avec la décision et part par la
    boîte d'envoi du backend ; le bot de l'admin n'envoie rien."""
    addition_id = _ask()
    callback = Callback(f"admin_addition_ok_{addition_id}", Bot(fail=True))
    asyncio.run(admin.admin_answer_addition(callback))
    assert callback.message.edited_text.startswith("✅ Approuvé")
    assert "service_nettoyage" in _services(live)
    assert len(_to_provider(live)) == 1
