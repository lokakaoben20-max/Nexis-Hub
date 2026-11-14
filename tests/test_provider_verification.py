"""Vérification obligatoire des prestataires (V5_MIGRATION_PLAN.md).

Un prestataire ne doit pas être matchable tant qu'un admin n'a pas approuvé sa pièce
d'identité et son selfie. Les décisions de l'admin passent par le backend, qui désigne le prestataire par
son compte Nexis (`admin_<action>_provider_acc_<compte>`).
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from telegram_bot import admin, registration


class DummyBot:
    def __init__(self):
        self.messages = []
        self.photos = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))

    async def send_photo(self, chat_id, photo, caption=None, **kwargs):
        self.photos.append((chat_id, caption))


class DummyMessageObject:
    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        pass

    async def answer(self, text, parse_mode=None, reply_markup=None):
        pass


class DummyUser:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Test"


class DummyCallback:
    def __init__(self, telegram_id, data="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessageObject()
        self.bot = bot or DummyBot()

    async def answer(self, text=None, show_alert=False):
        pass


class DummyMessage:
    def __init__(self, telegram_id, photo=True):
        self.from_user = DummyUser(telegram_id)
        self.photo = [type("P", (), {"file_id": f"file_{telegram_id}"})] if photo else None
        self.text = None
        self.voice = None

    async def answer(self, text, parse_mode=None, reply_markup=None):
        pass


class DummyState:
    def __init__(self, data=None):
        self._data = data or {}

    async def get_data(self):
        return self._data

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        pass

    async def clear(self):
        self._data = {}


ADMIN = 999


def test_pending_verification_provider_is_never_alerted(live_backend):
    live_backend.provider(1001, verified=False, services=["service_plomberie"], communes=["Gombe"])

    mission_id = live_backend.new_mission(42, service="service_plomberie", commune="Gombe")

    assert live_backend.alerted(mission_id) == [], "pending_verification reste invisible du matching"


def test_full_registration_collects_documents_and_starts_pending(live_backend):
    telegram_id = 1010
    state = DummyState(data={
        "provider_phone": "+243800001010",
        "provider_full_name": "Nouveau Prestataire",
        "provider_services": ["service_plomberie"],
        "provider_communes": ["Gombe"],
        "language": "fr",
    })

    # communes -> id_document
    asyncio.run(registration.terminer_inscription_prestataire(DummyCallback(telegram_id, "provider_communes_done"), state))

    # id_document photo -> selfie
    asyncio.run(registration.recevoir_document_identite(DummyMessage(telegram_id), state))
    assert state._data["provider_id_document_file_id"] == f"file_{telegram_id}"

    # selfie photo -> portfolio
    asyncio.run(registration.recevoir_selfie(DummyMessage(telegram_id), state))
    assert state._data["provider_selfie_file_id"] == f"file_{telegram_id}"

    # skip portfolio directly -> finalisation
    callback = DummyCallback(telegram_id, "provider_portfolio_done")
    asyncio.run(registration.finaliser_inscription_prestataire(callback, state))

    provider = live_backend.profile(telegram_id)["provider"]
    assert provider["status"] == "pending_verification", "ne doit jamais devenir 'available' directement à l'inscription"
    assert provider["is_verified"] is False

    mission_id = live_backend.new_mission(42, service="service_plomberie", commune="Gombe")
    assert live_backend.alerted(mission_id) == []


def test_admin_verify_provider_makes_him_matchable(live_backend):
    live_backend.grant_admin(ADMIN)
    account_id = live_backend.provider(1020, "A Verifier", verified=False, services=["service_plomberie"], communes=["Gombe"])
    dummy_bot = DummyBot()

    asyncio.run(admin.admin_verify_provider(DummyCallback(ADMIN, data=f"admin_verify_provider_acc_{account_id}", bot=dummy_bot)))

    assert live_backend.profile(1020)["provider"]["status"] == "available"
    mission_id = live_backend.new_mission(42, service="service_plomberie", commune="Gombe")
    assert live_backend.alerted(mission_id) == [1020], "matchable après approbation"
    assert [chat_id for chat_id, _ in dummy_bot.messages] == [1020], "le prestataire est notifié"


def test_admin_reject_provider_keeps_provider_excluded(live_backend):
    live_backend.grant_admin(ADMIN)
    account_id = live_backend.provider(1030, "A Refuser", verified=False, services=["service_plomberie"], communes=["Gombe"])
    dummy_bot = DummyBot()

    asyncio.run(admin.admin_reject_provider(DummyCallback(ADMIN, data=f"admin_reject_provider_acc_{account_id}", bot=dummy_bot)))

    assert live_backend.profile(1030)["provider"]["status"] == "rejected"
    mission_id = live_backend.new_mission(42, service="service_plomberie", commune="Gombe")
    assert live_backend.alerted(mission_id) == []
    assert dummy_bot.messages


def test_an_old_button_with_a_telegram_id_decides_nothing(live_backend):
    """Les anciens boutons (id Telegram ou numéro SQLite) ne désignent
    personne de façon sûre : refusés, rien ne change."""
    live_backend.grant_admin(ADMIN)
    live_backend.provider(1040, verified=False)
    dummy_bot = DummyBot()

    asyncio.run(admin.admin_verify_provider(DummyCallback(ADMIN, data="admin_verify_provider_1040", bot=dummy_bot)))

    assert live_backend.profile(1040)["provider"]["status"] == "pending_verification"
    assert dummy_bot.messages == []
