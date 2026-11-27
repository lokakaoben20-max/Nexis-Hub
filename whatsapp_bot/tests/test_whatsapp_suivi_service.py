"""Service WhatsApp, étape 7 : suivi d'une demande payée (arrivée, fin,
problème, avis) et « Mon solde ».

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis). Le prestataire agit depuis Telegram, comme en vrai.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from messages import get_message
from whatsapp_bot import paiement, suivi
from whatsapp_bot.tests.conftest import TELEGRAM_KEY, run, verified_provider
from whatsapp_bot.tests.test_whatsapp_demande import _choices
from whatsapp_bot.tests.test_whatsapp_devis import _mission
from whatsapp_bot.tests.test_whatsapp_payer import _accepted, _credit

pytestmark = pytest.mark.conditions_reelles

PROVIDER = 7


def _as_provider(main, method, path):
    headers = {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": str(PROVIDER)}
    with TestClient(main.app) as api:
        response = api.request(method, path, headers=headers)
    assert response.status_code == 200, response.json()
    return response.json()


async def _paid(bench):
    """Demande WhatsApp payée par le wallet : rend son numéro."""
    verified_provider(bench.main)
    _answer, quote_id = await _accepted(bench)
    _credit(bench.main, 100)
    await bench.tap(f"{paiement.PAY_WALLET}{quote_id}")
    return _mission(bench.main).mission_id


async def _view(bench, mission_id):
    return await bench.tap(f"mis:{mission_id}")


def _buttons(messages):
    return [message for message in messages if message.kind == "button"]


def _settlements(main, mission_id):
    from backend.app.ledger import SETTLEMENT, MoneyOperation

    with main.database.SessionLocal() as db:
        return [row.kind for row in db.execute(select(MoneyOperation).filter_by(mission_id=mission_id, phase=SETTLEMENT)).scalars()]


def _code(main, mission_id):
    from backend.app import presence

    return presence.presence_code(mission_id)


async def _in_progress(bench, mission_id):
    _as_provider(bench.main, "POST", f"/api/bot/missions/{mission_id}/presence/arrived")
    await bench.tap(f"{suivi.PRESENCE_YES}{mission_id}")


async def _finished(bench, mission_id):
    await _in_progress(bench, mission_id)
    _as_provider(bench.main, "POST", f"/api/bot/missions/{mission_id}/finish")


# --- Arrivée ---------------------------------------------------------------------------


def test_a_paid_request_shows_the_presence_code_then_asks_once_the_provider_says_he_arrived(bench):
    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            shown = await _view(bench, mission_id)
            code_line = [message for message in shown if _code(bench.main, mission_id) in (message.text or "")]
            assert code_line and code_line[0].kind == "text"  # rien à répondre avant l'arrivée
            assert not _buttons(shown)

            _as_provider(bench.main, "POST", f"/api/bot/missions/{mission_id}/presence/arrived")
            shown = await _view(bench, mission_id)
            card = _buttons(shown)[-1]
            assert _code(bench.main, mission_id) in card.text
            assert _choices([card]) == [f"{prefix}{mission_id}" for prefix in (suivi.PRESENCE_YES, suivi.PRESENCE_NOT_YET, suivi.PRESENCE_WRONG)]

            later = await bench.tap(f"{suivi.PRESENCE_NOT_YET}{mission_id}")
            assert later[0].text == get_message("wa_presence_not_yet", "fr")
            assert _mission(bench.main).status == "confirmed"
            yes = await bench.tap(f"{suivi.PRESENCE_YES}{mission_id}")
            assert yes[0].text.startswith("✅") and "NXH-0001" in yes[0].text
            assert _mission(bench.main).status == "in_progress"
            again = await bench.tap(f"{suivi.PRESENCE_YES}{mission_id}")
            assert again[0].text == yes[0].text  # rien de plus
            shown = await _view(bench, mission_id)
            assert _code(bench.main, mission_id) not in "".join(message.text or "" for message in shown)
            assert _choices(_buttons(shown)) == [f"{suivi.ISSUE}{mission_id}"]

    run(scenario)


def test_not_this_person_asks_first_then_freezes_the_money(bench):
    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            _as_provider(bench.main, "POST", f"/api/bot/missions/{mission_id}/presence/arrived")
            asked = await bench.tap(f"{suivi.PRESENCE_WRONG}{mission_id}")
            assert _choices(asked) == [f"{suivi.PRESENCE_WRONG_OK}{mission_id}", f"mis:{mission_id}"]
            assert _mission(bench.main).status == "confirmed"  # rien n'est fait avant la confirmation
            back = await bench.tap(f"mis:{mission_id}")
            assert _buttons(back)  # la question revient
            done = await bench.tap(f"{suivi.PRESENCE_WRONG_OK}{mission_id}")
            assert done[0].text.startswith("🛑")
            assert _mission(bench.main).status == "disputed"
            assert _settlements(bench.main, mission_id) == []
            shown = await _view(bench, mission_id)
            assert any(message.text.startswith("⚖️") for message in shown if message.kind in ("text", "button"))
            late = await bench.tap(f"{suivi.DONE_OK}{mission_id}")
            assert late[0].text == get_message("wa_follow_changed", "fr")
            assert _settlements(bench.main, mission_id) == []

    run(scenario)


# --- Fin du travail et avis ----------------------------------------------------------


def test_confirming_the_end_asks_first_pays_once_then_offers_the_rating(bench):
    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            await _finished(bench, mission_id)
            shown = await _view(bench, mission_id)
            assert _choices(_buttons(shown)[-1:]) == [f"{suivi.DONE}{mission_id}", f"{suivi.ISSUE}{mission_id}"]
            asked = await bench.tap(f"{suivi.DONE}{mission_id}")
            assert _choices(asked) == [f"{suivi.DONE_OK}{mission_id}", f"mis:{mission_id}"]
            assert _settlements(bench.main, mission_id) == []

            payload = bench.fake.choice_message(f"{suivi.DONE_OK}{mission_id}")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500  # réponse perdue : Meta renvoie le message
            assert (await bench.post(payload)).status_code == 200
            released = bench.fake.sent[-2:]
            assert released[0].text.startswith("✅") and released[-1].kind == "list"
            again = await bench.tap(f"{suivi.DONE_OK}{mission_id}")
            assert again[0].text == released[0].text
            assert _settlements(bench.main, mission_id) == ["release"]
            assert _mission(bench.main).status == "completed"

            await bench.tap(f"{suivi.RATE_STAR}{mission_id}:4")
            thanks = await bench.say("Travail propre, merci")
            assert thanks[0].text == get_message("wa_rate_thanks", "fr")
            from backend.app.models import BotReview

            with bench.main.database.SessionLocal() as db:
                review = db.execute(select(BotReview)).scalar_one()
                assert (review.rating, review.comment, review.client_telegram_id) == (4, "Travail propre, merci", None)
            shown = await _view(bench, mission_id)
            assert not _buttons(shown)  # « Noter » n'est plus proposé
            twice = await bench.tap(f"{suivi.RATE}{mission_id}")
            await bench.tap(f"{suivi.RATE_STAR}{mission_id}:1")
            refused = await bench.tap(f"{suivi.RATE_SKIP}{mission_id}")
            assert twice[0].kind == "list" and refused[0].text == get_message("wa_rate_already", "fr")

    run(scenario)


def test_rating_can_skip_the_comment_and_an_old_skip_button_asks_the_stars_again(bench):
    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            await _finished(bench, mission_id)
            await bench.tap(f"{suivi.DONE_OK}{mission_id}")
            await bench.tap(f"{suivi.RATE_STAR}{mission_id}:5")
            photo = await bench.send_media()
            assert photo[0].text == get_message("wa_media_refused", "fr") and photo[-1].kind == "button"
            done = await bench.tap(f"{suivi.RATE_SKIP}{mission_id}")
            assert done[0].text == get_message("wa_rate_thanks", "fr")
            old = await bench.tap(f"{suivi.RATE_SKIP}{mission_id}")
            assert old[0].kind == "list"  # la note choisie n'est plus connue : on la redemande
            from backend.app.models import BotReview

            with bench.main.database.SessionLocal() as db:
                assert [(row.rating, row.comment) for row in db.execute(select(BotReview)).scalars()] == [(5, None)]

    run(scenario)


# --- Problème ------------------------------------------------------------------------------


def test_reporting_a_problem_takes_a_reason_then_words_and_freezes_the_money_once(bench):
    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            await _finished(bench, mission_id)
            reasons = await bench.tap(f"{suivi.ISSUE}{mission_id}")
            assert reasons[0].kind == "list"
            assert _choices(reasons) == [f"{suivi.ISSUE_REASON}{mission_id}:{reason}" for reason in suivi.ISSUE_REASONS]
            await bench.tap(f"{suivi.ISSUE_REASON}{mission_id}:unfinished")
            payload = bench.fake.text_message("La cuisine n'est pas faite")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500
            assert (await bench.post(payload)).status_code == 200
            assert bench.fake.sent[-2].text.startswith("⚖️")
            assert _mission(bench.main).status == "disputed"
            assert _mission(bench.main).dispute_reason == "Travail pas terminé : La cuisine n'est pas faite"
            assert _settlements(bench.main, mission_id) == []
            after = await bench.say("Bonjour")
            assert after[-1].kind == "list"  # l'étape est finie : le menu
            assert _mission(bench.main).dispute_reason.endswith("pas faite")

    run(scenario)


def test_a_problem_reported_after_the_payment_is_explained(bench):
    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            await _finished(bench, mission_id)
            await bench.tap(f"{suivi.ISSUE_REASON}{mission_id}:damage")
            await bench.tap(f"{suivi.DONE_OK}{mission_id}")  # payé entre-temps (autre appui)
            await bench.tap(f"{suivi.ISSUE_REASON}{mission_id}:damage")
            late = await bench.say("Vase cassé")
            assert late[0].text == get_message("wa_follow_already_released", "fr", reference="NXH-0001")
            assert _mission(bench.main).status == "completed"

    run(scenario)


# --- Autres clients, « Mon solde » ------------------------------------------------------


def test_nobody_else_can_act_on_the_request(bench):
    other = {"bsuid": "CD.3000000000000000003", "phone": "243810000003"}

    async def scenario():
        async with bench:
            mission_id = await _paid(bench)
            _as_provider(bench.main, "POST", f"/api/bot/missions/{mission_id}/presence/arrived")
            await bench.register(name="Autre", **other)
            for choice in (f"{suivi.PRESENCE_YES}{mission_id}", f"{suivi.PRESENCE_WRONG_OK}{mission_id}", f"{suivi.DONE_OK}{mission_id}"):
                answer = await bench.tap(choice, **other)
                assert answer[0].text == get_message("wa_mission_unknown", "fr")
                assert "NXH-0001" not in answer[0].text
            assert _mission(bench.main).status == "confirmed"

    run(scenario)


def test_my_balance_shows_the_wallet_and_its_latest_movements(bench):
    async def scenario():
        async with bench:
            await bench.register()
            empty = await bench.tap("menu:wallet")
            assert "0.00 USD" in empty[0].text and get_message("wa_wallet_no_history", "fr") in empty[0].text
            await _paid_after_register(bench)
            shown = await bench.tap("menu:wallet")
            assert "60.00 USD" in shown[0].text
            assert get_message("wa_history_fund_wallet", "fr") + " (NXH-0001) : -40.00 USD" in shown[0].text
            assert get_message("wa_history_opening_balance", "fr") + " : +100.00 USD" in shown[0].text
            assert shown[-1].kind == "list"

    run(scenario)


async def _paid_after_register(bench):
    from whatsapp_bot.tests.conftest import provider_quote
    from whatsapp_bot.tests.test_whatsapp_demande import _up_to_recap

    verified_provider(bench.main)
    await _up_to_recap(bench)
    await bench.tap("m:confirm")
    quote_id = provider_quote(bench.main, _mission(bench.main).mission_id)
    await bench.tap(f"quote_accept_{quote_id}")
    _credit(bench.main, 100)
    await bench.tap(f"{paiement.PAY_WALLET}{quote_id}")
