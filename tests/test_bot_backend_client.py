"""Client du backend dans le bot : la langue et le profil viennent du seul
backend ; une panne se voit (jamais une valeur inventée qui ferait agir)."""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import pytest

from telegram_bot import backend_client, dashboard, payment
from telegram_bot.backend_client import BackendUnavailable, MoneyRefused


def test_get_language_reads_the_account_language(live_backend):
    live_backend.client(42, language="ln")

    assert asyncio.run(backend_client.get_language(42)) == "ln"


def test_get_language_of_an_unknown_person_is_french(live_backend):
    assert asyncio.run(backend_client.get_language(43)) == "fr"
    assert live_backend.profile(43)["profile_type"] == "guest", "lire la langue ne crée aucun profil"


def test_get_language_falls_back_to_french_when_the_backend_is_down():
    assert asyncio.run(backend_client.get_language(42)) == "fr"


class TelegramUser:
    def __init__(self, telegram_id, language_code):
        self.id = telegram_id
        self.language_code = language_code


def test_without_the_backend_the_telegram_language_is_used():
    assert asyncio.run(backend_client.get_language(TelegramUser(42, "en-GB"))) == "en"
    assert asyncio.run(backend_client.get_language(TelegramUser(42, "de"))) == "fr", "hors des langues de Nexis : français"


def test_a_new_person_gets_the_telegram_language_until_she_chooses(live_backend):
    assert asyncio.run(backend_client.get_language(TelegramUser(45, "ln"))) == "ln"

    live_backend.client(45, language="fr")
    assert asyncio.run(backend_client.get_language(TelegramUser(45, "ln"))) == "fr", "le choix du compte prime"


def test_my_profile_is_none_when_the_backend_is_down():
    assert asyncio.run(backend_client.my_profile(42)) is None


def test_fetch_me_raises_when_the_backend_is_down():
    with pytest.raises(BackendUnavailable):
        asyncio.run(backend_client.fetch_me(42))


def test_a_refusal_carries_the_backend_code(live_backend):
    with pytest.raises(MoneyRefused) as refusal:
        asyncio.run(backend_client.set_my_availability(44, "available"))

    assert refusal.value.code == "provider_not_found"


def test_safe_backend_call_swallows_network_errors():
    result = asyncio.run(backend_client._safe_backend_call(backend_client.sync_review_to_backend(1, 42, 5)))

    assert result is None


class DummyState:
    def __init__(self):
        self.cleared = False

    async def clear(self):
        self.cleared = True


def test_finalize_review_clears_state_after_backend_success(monkeypatch):
    async def save_review(*args, **kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(payment, "sync_review_to_backend", save_review)
    state = DummyState()

    result = asyncio.run(payment._finalize_review(42, {"rating_mission_id": 1, "rating_value": 5}, "Excellent", state))

    assert result == {"status": "ok"}
    assert state.cleared is True


def test_finalize_review_keeps_state_when_backend_is_unavailable(monkeypatch):
    async def save_review(*args, **kwargs):
        raise RuntimeError("backend unreachable")

    monkeypatch.setattr(payment, "sync_review_to_backend", save_review)
    state = DummyState()

    result = asyncio.run(payment._finalize_review(42, {"rating_mission_id": 1, "rating_value": 5}, None, state))

    assert result is None
    assert state.cleared is False


def test_backend_mission_is_rendered_without_legacy_only_fields():
    mission = {
        "mission_id": 17,
        "service": "service_plomberie",
        "commune": "Gombe",
        "status": "completed",
        "payment_status": "released",
    }

    rendered = dashboard.format_mission_client(mission)
    rich_message = dashboard.build_history_rich_message("fr", [mission])

    assert "NXH-0017" in rendered
    assert "Non attribué" in rendered
    assert rich_message.blocks
