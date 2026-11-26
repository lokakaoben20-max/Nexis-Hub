"""Service WhatsApp, étape 6 (première partie) : « Mes demandes » et devis.

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from messages import get_message
from whatsapp_bot import devis
from whatsapp_bot.fake_meta import DEFAULT_BSUID
from whatsapp_bot.tests.conftest import provider_quote, publish_terms, run, verified_provider
from whatsapp_bot.tests.test_whatsapp_demande import _choices, _up_to_recap

pytestmark = pytest.mark.conditions_reelles

OTHER_BSUID = "CD.2000000000000000002"


def _quotes(main):
    from backend.app.models import BotQuote

    with main.database.SessionLocal() as db:
        return {quote.id: quote.status for quote in db.execute(select(BotQuote)).scalars()}


def _mission(main):
    from backend.app.models import BotMission

    with main.database.SessionLocal() as db:
        return db.execute(select(BotMission)).scalars().one()


async def _mission_on_whatsapp(bench):
    await bench.register()
    await _up_to_recap(bench)
    await bench.tap("m:confirm")
    return _mission(bench.main).mission_id


def test_my_requests_lists_the_missions_and_shows_the_quotes(bench):
    verified_provider(bench.main, telegram_id=7)
    verified_provider(bench.main, telegram_id=8)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            empty = await bench.tap(f"mis:{mission_id}")
            assert get_message("wa_no_quotes_yet", "fr") in [message.text for message in empty]
            first = provider_quote(bench.main, mission_id, telegram_id=7, amount=40)
            second = provider_quote(bench.main, mission_id, telegram_id=8, amount=12500, currency="CDF")
            listed = (await bench.tap("menu:missions"))[-1]
            assert listed.kind == "list"
            assert listed.choices[0] == (f"mis:{mission_id}", "NXH-0001 Nettoyage")
            shown = await bench.tap(f"mis:{mission_id}")
            assert "NXH-0001" in shown[0].text and get_message("wa_status_quoted", "fr") in shown[0].text
            cards = [message for message in shown if message.kind == "button"]
            assert [_choices([card]) for card in cards] == [
                [f"quote_accept_{first}", f"quote_reject_{first}"],
                [f"quote_accept_{second}", f"quote_reject_{second}"],
            ]
            assert "40.00 USD" in cards[0].text and "Prestataire 7" in cards[0].text
            assert "12 500 FC" in cards[1].text
            assert get_message("wa_trust_verified", "fr").strip(" ·") in cards[0].text
            assert shown[-1].kind == "list"  # menu

    run(scenario)


def test_accepting_a_quote_confirms_the_mission_and_rejects_the_others(bench):
    verified_provider(bench.main, telegram_id=7)
    verified_provider(bench.main, telegram_id=8)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            first = provider_quote(bench.main, mission_id, telegram_id=7, amount=40)
            second = provider_quote(bench.main, mission_id, telegram_id=8, amount=55)
            accepted = await bench.tap(f"quote_accept_{second}")
            assert accepted[0].text.startswith("✅")
            assert "NXH-0001" in accepted[0].text and "55.00 USD" in accepted[0].text
            assert "Prestataire 8" in accepted[0].text
            assert _quotes(bench.main) == {first: "rejected", second: "accepted"}
            assert _mission(bench.main).status == "confirmed"
            # La demande montre maintenant le devis accepté, sans boutons.
            shown = await bench.tap(f"mis:{mission_id}")
            assert get_message("wa_status_confirmed_unpaid", "fr") in shown[0].text
            assert not [message for message in shown if message.kind == "button"]
            # L'ancien bouton de l'autre devis : il n'est plus ouvert.
            late = await bench.tap(f"quote_accept_{first}")
            assert late[0].text == get_message("wa_quote_closed", "fr")
            assert _quotes(bench.main) == {first: "rejected", second: "accepted"}

    run(scenario)


def test_rejecting_a_quote(bench):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            quote_id = provider_quote(bench.main, mission_id)
            rejected = await bench.tap(f"quote_reject_{quote_id}")
            assert rejected[0].text == get_message("wa_quote_rejected", "fr", reference="NXH-0001")
            assert _quotes(bench.main) == {quote_id: "rejected"}

    run(scenario)


def test_a_replayed_accept_after_a_lost_answer_decides_once(bench):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            quote_id = provider_quote(bench.main, mission_id)
            payload = bench.fake.choice_message(f"quote_accept_{quote_id}")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500
            assert (await bench.post(payload)).status_code == 200
            assert bench.fake.sent[-2].text.startswith("✅")
            # Un second appui (autre message) : même réponse, rien de plus.
            again = await bench.tap(f"quote_accept_{quote_id}")
            assert again[0].text.startswith("✅")

    run(scenario)
    from backend.app.models import Notification

    with bench.main.database.SessionLocal() as db:
        sent_to_provider = db.query(Notification).filter(Notification.message_key == "quote_accept_provider_notify").count()
    assert sent_to_provider == 1


def test_someone_else_cannot_decide_or_read(bench):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            quote_id = provider_quote(bench.main, mission_id)
            await bench.register(name="Autre", bsuid=OTHER_BSUID, phone="243810000002")
            refused = await bench.tap(f"quote_accept_{quote_id}", bsuid=OTHER_BSUID, phone="243810000002")
            assert refused[0].text == get_message("wa_quote_unknown", "fr")
            hidden = await bench.tap(f"mis:{mission_id}", bsuid=OTHER_BSUID, phone="243810000002")
            assert hidden[0].text == get_message("wa_mission_unknown", "fr")
            assert _quotes(bench.main) == {quote_id: "pending"}

    run(scenario)


def test_new_terms_are_accepted_before_the_quote(bench):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            quote_id = provider_quote(bench.main, mission_id)
            now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            publish_terms(bench.main, "2026-12-01", at=now, documents=("cgu",))
            asked = await bench.tap(f"quote_accept_{quote_id}")
            assert _choices(asked[-1:]) == [devis.TERMS_ACCEPT, devis.TERMS_DECLINE]
            assert _quotes(bench.main) == {quote_id: "pending"}
            shown = await bench.tap(devis.TERMS_ACCEPT)
            # Le devis est remontré : la personne décide par un nouvel appui.
            assert f"quote_accept_{quote_id}" in _choices(shown)
            assert _quotes(bench.main) == {quote_id: "pending"}
            assert (await bench.tap(f"quote_accept_{quote_id}"))[0].text.startswith("✅")

    run(scenario)
    assert _quotes(bench.main) == {next(iter(_quotes(bench.main))): "accepted"}


def test_no_request_yet(bench):
    async def scenario():
        async with bench:
            await bench.register()
            sent = await bench.tap("menu:missions")
            assert sent[0].text == get_message("wa_no_missions", "fr")

    run(scenario)


def test_a_quote_button_during_a_new_request_answers_the_quote(bench):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            quote_id = provider_quote(bench.main, mission_id)
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            accepted = await bench.tap(f"quote_accept_{quote_id}")
            assert accepted[0].text.startswith("✅")
            return await bench.store.conversation(DEFAULT_BSUID)

    assert run(scenario) == {}


@pytest.mark.parametrize("lang", ["fr", "ln", "en"])
def test_quote_screens_respect_whatsapp_limits(bench, lang):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            await bench.register(language=lang)
            await _up_to_recap(bench)
            await bench.tap("m:confirm")
            mission_id = _mission(bench.main).mission_id
            provider_quote(bench.main, mission_id, message="Très long message. " * 60)
            # Le faux Meta refuserait un écran hors limites (réponse 500).
            await bench.tap("menu:missions")
            shown = await bench.tap(f"mis:{mission_id}")
            assert any(message.kind == "button" for message in shown)

    run(scenario)


def test_amounts_are_shown_like_the_backend():
    assert devis.amount_text(40, "USD") == ("40.00", "USD")
    assert devis.amount_text(12500, "CDF") == ("12 500", "FC")
    assert devis.amount_text("19.5", "USD") == ("19.50", "USD")
