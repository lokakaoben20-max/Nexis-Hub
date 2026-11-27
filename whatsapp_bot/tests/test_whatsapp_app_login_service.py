"""Connexion à l'application par WhatsApp, côté service (étape 8, seconde
partie), contre le faux Meta : le message déjà écrit par le lien de l'app
est reconnu, le code arrive dans la conversation (envoyé par le backend, à
l'identité qui écrit), et chaque refus a sa phrase. La conversation en cours
n'est pas interrompue.
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

import pytest

from messages import get_message
from whatsapp_bot.fake_meta import DEFAULT_BSUID, DEFAULT_PHONE
from whatsapp_bot.tests.conftest import run
from whatsapp_bot.tests.test_whatsapp_demande import _choices
from whatsapp_bot.tests.test_whatsapp_notifications_service import _sender

pytestmark = pytest.mark.conditions_reelles

DEVICE = "c" * 64


@pytest.fixture
def login(bench, monkeypatch):
    """L'app demande un code par WhatsApp ; rend le message déjà écrit."""
    from backend.app import app_auth

    _sender(bench, monkeypatch)
    monkeypatch.setenv("APP_CODE_HMAC_KEY", "test-hmac-key-not-a-secret-0123456789abcdef")
    monkeypatch.setenv(app_auth.WHATSAPP_NUMBER_ENV, "243990000000")

    def ask(phone=f"+{DEFAULT_PHONE}", language="fr"):
        with bench.main.database.SessionLocal() as db:
            created = app_auth.create_challenge(db, phone=phone, delivery="whatsapp", device_key_thumbprint=DEVICE)
        prefill = get_message("wa_app_login_prefill", language, start=app_auth.telegram_start_payload(created.start_token))
        return created, prefill

    return ask


def _code(message) -> str:
    return re.search(r"\*(\d{6})\*", message.text).group(1)


def test_the_message_from_the_app_link_brings_the_code_to_this_whatsapp(bench, login):
    from backend.app import app_auth

    created, prefill = login(language="ln")

    async def scenario():
        async with bench:
            sent = await bench.say(prefill)
            (message,) = sent
            assert message.recipient == DEFAULT_BSUID and message.to is None
            return _code(message)

    code = run(scenario)
    with bench.main.database.SessionLocal() as db:
        verified = app_auth.verify_code(db, public_id=created.public_id, code=code, device_key_thumbprint=DEVICE)
    assert verified.existing_account is False


def test_a_hidden_number_is_told_to_use_telegram(bench, login):
    _created, prefill = login()

    async def scenario():
        async with bench:
            (message,) = await bench.say(prefill, phone=None)
            assert message.text == get_message("app_login_phone_hidden", "fr")

    run(scenario)


def test_a_link_for_another_number_or_already_used_is_refused_with_its_sentence(bench, login):
    _created, prefill = login(phone="+243810000077")

    async def scenario():
        async with bench:
            (message,) = await bench.say(prefill)
            assert message.text == get_message("app_login_phone_mismatch", "fr")

    run(scenario)

    _created, prefill = login()

    async def again():
        async with bench:
            await bench.say(prefill)
            (message,) = await bench.say(prefill)
            assert message.text == get_message("app_login_link_invalid", "fr")

    run(again)


def test_someone_else_writing_for_a_proven_number_gets_nothing(bench, login):
    async def register():
        async with bench:
            await bench.register()

    run(register)
    _created, prefill = login(language="en")

    async def scenario():
        async with bench:
            (message,) = await bench.say(prefill, bsuid="CD.1000000000000000099")
            assert message.text == get_message("app_login_phone_conflict", "en")
            assert not re.search(r"\d{6}", message.text)

    run(scenario)


def test_the_conversation_in_progress_is_kept(bench, login):
    from whatsapp_bot import demande

    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            urgent = await bench.tap("svc:service_nettoyage")
            _created, prefill = login()
            sent = await bench.say(prefill)
            assert len(sent) == 1 and _code(sent[0])
            # La demande en cours reprend où elle était : l'urgence, puis les communes.
            communes = await bench.tap(demande.URGENT_NO)
            assert "com:Gombe" in _choices(communes) and _choices(urgent)

    run(scenario)


def test_the_prepared_message_is_a_wa_me_link_with_the_token_only():
    from backend.app import app_auth

    prefill = get_message("wa_app_login_prefill", "fr", start=app_auth.telegram_start_payload("x" * 32))
    url = urlparse(f"https://wa.me/243990000000?{'text=' + prefill}")
    assert parse_qs(url.query)["text"][0].endswith("app_" + "x" * 32)


def test_a_token_hidden_in_another_text_is_not_a_login(bench, login):
    """Lien piégé (« Je participe au tirage app_… ») : rien ne part, la
    conversation continue comme pour tout autre message."""
    created, prefill = login()
    token = prefill.rsplit(" ", 1)[1]

    async def scenario():
        async with bench:
            sent = await bench.say(f"Je participe au tirage NexisHub {token}")
            assert not any(re.search(r"\*\d{6}\*", message.text or "") for message in sent)

    run(scenario)
    with bench.main.database.SessionLocal() as db:
        from backend.app.models import LoginChallenge

        assert db.query(LoginChallenge).filter_by(public_id=created.public_id).one().code_hash is None
