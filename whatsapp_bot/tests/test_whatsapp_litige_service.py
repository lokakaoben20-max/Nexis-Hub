"""Service WhatsApp, étape 7b : litige d'une demande (contester la décision de
NexisHub, proposer un accord amiable).

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis). Le prestataire et l'équipe agissent hors de WhatsApp, comme en vrai.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from messages import get_message
from whatsapp_bot import litige, suivi
from whatsapp_bot.tests.conftest import run
from whatsapp_bot.tests.test_whatsapp_demande import _choices
from whatsapp_bot.tests.test_whatsapp_devis import _mission
from whatsapp_bot.tests.test_whatsapp_suivi_service import _as_provider, _buttons, _finished, _paid, _settlements, _view

pytestmark = pytest.mark.conditions_reelles

ADMIN_TELEGRAM = 900


async def _disputed(bench):
    mission_id = await _paid(bench)
    await _finished(bench, mission_id)
    await bench.tap(f"{suivi.ISSUE_REASON}{mission_id}:unfinished")
    await bench.say("La cuisine n'est pas faite")
    assert _mission(bench.main).status == "disputed"
    return mission_id


def _decide(main, mission_id, decision="split", percentage=40):
    from backend.app import ledger

    with main.database.SessionLocal() as db:
        admin = ledger.account_id_for(db, ledger.TELEGRAM, ADMIN_TELEGRAM, create=True)
        db.commit()
        ledger.decide_dispute(
            db, mission_id, decision=decision, admin_account_id=admin, admin_telegram_id=ADMIN_TELEGRAM, provider_percentage=percentage
        )
        return ledger.dispute_decisions(db, mission_id)[0]


def _offers(main):
    from backend.app.models import DisputeSettlementOffer

    with main.database.SessionLocal() as db:
        return [(row.kind, row.provider_percentage, row.status) for row in db.execute(select(DisputeSettlementOffer)).scalars()]


def _notifications(main, prefix):
    from backend.app.models import Notification

    with main.database.SessionLocal() as db:
        return db.query(Notification).filter(Notification.event_key.like(f"{prefix}%")).count()


# --- Accord amiable -----------------------------------------------------------------------


def test_the_client_offers_a_split_once_and_sees_the_amounts_from_the_backend(bench):
    async def scenario():
        async with bench:
            mission_id = await _disputed(bench)
            shown = await _view(bench, mission_id)
            assert _choices(_buttons(shown)) == [f"{litige.OFFER_NEW}{mission_id}"]
            kinds = await bench.tap(f"{litige.OFFER_NEW}{mission_id}")
            assert _choices(kinds) == [f"{litige.OFFER}{mission_id}:{kind}" for kind in litige.OFFER_KINDS]
            shares = await bench.tap(f"{litige.OFFER}{mission_id}:split")
            assert _choices(shares) == [f"{litige.OFFER}{mission_id}:split{pct}" for pct in (25, 50, 75)]
            card = await bench.tap(f"{litige.OFFER}{mission_id}:split50")
            assert "50 %" in card[0].text
            assert _choices(card) == [f"{litige.OFFER_SEND}{mission_id}:split50", f"mis:{mission_id}"]
            assert _offers(bench.main) == []  # rien n'est envoyé avant « Envoyer »

            payload = bench.fake.choice_message(f"{litige.OFFER_SEND}{mission_id}:split50")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500  # réponse perdue : Meta renvoie le message
            assert (await bench.post(payload)).status_code == 200
            sent = bench.fake.sent[-2]
            assert sent.text.startswith("✅") and "NXH-0001" in sent.text
            assert "USD" in sent.text and "•" in sent.text  # montants calculés par le backend
            again = await bench.tap(f"{litige.OFFER_SEND}{mission_id}:split50")
            assert again[0].text == sent.text
            assert [(kind, float(pct), status) for kind, pct, status in _offers(bench.main)] == [("split", 50.0, "pending")]
            assert _notifications(bench.main, "offer_proposed:") == 1

            other = await bench.tap(f"{litige.OFFER_SEND}{mission_id}:refund")
            assert other[0].text == get_message("wa_offer_already_pending", "fr")
            shown = await _view(bench, mission_id)
            assert any("attend la réponse" in (message.text or "") for message in shown)
            assert not _buttons(shown)

            from backend.app.models import DisputeSettlementOffer

            with bench.main.database.SessionLocal() as db:
                offer_id = db.execute(select(DisputeSettlementOffer.id)).scalar_one()
            _as_provider(bench.main, "POST", f"/api/bot/missions/{mission_id}/dispute/offers/{offer_id}/accept")
            assert _settlements(bench.main, mission_id) == ["agreement"]

    run(scenario)


# --- Contester la décision ---------------------------------------------------------------


def test_the_client_contests_the_decision_with_a_reason_once(bench):
    async def scenario():
        async with bench:
            mission_id = await _disputed(bench)
            decision = _decide(bench.main, mission_id)
            shown = await _view(bench, mission_id)
            card = _buttons(shown)[-1]
            assert _choices([card]) == [f"{litige.CONTEST}{mission_id}"]
            assert f"{decision.client_amount:.2f} USD" in card.text and f"{decision.provider_amount:.2f} USD" in card.text

            old_offer = await bench.tap(f"{litige.OFFER_SEND}{mission_id}:redo")
            assert old_offer[0].text == get_message("wa_follow_changed", "fr")  # décision prise : plus d'accord
            assert _offers(bench.main) == []

            prompt = await bench.tap(f"{litige.CONTEST}{mission_id}")
            assert prompt[0].text.startswith("✏️")
            photo = await bench.send_media()
            assert photo[0].text == get_message("wa_media_refused", "fr")
            payload = bench.fake.text_message("Le prestataire n'a rien fini")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500
            assert (await bench.post(payload)).status_code == 200
            assert bench.fake.sent[-2].text.startswith("✅")
            assert _notifications(bench.main, f"dispute_contested:{decision.id}") == 1
            shown = await _view(bench, mission_id)
            assert any(message.text.startswith("⚖️") and "contestée" in message.text for message in shown if message.kind == "text")
            assert not _buttons(shown)
            assert _settlements(bench.main, mission_id) == []

    run(scenario)


def test_nobody_else_can_contest_or_offer(bench):
    other = {"bsuid": "CD.3000000000000000003", "phone": "243810000003"}

    async def scenario():
        async with bench:
            mission_id = await _disputed(bench)
            await bench.register(name="Autre", **other)
            offered = await bench.tap(f"{litige.OFFER_SEND}{mission_id}:refund", **other)
            assert offered[0].text == get_message("wa_mission_unknown", "fr")
            _decide(bench.main, mission_id)
            await bench.tap(f"{litige.CONTEST}{mission_id}", **other)
            contested = await bench.say("Je conteste", **other)
            assert contested[0].text == get_message("wa_mission_unknown", "fr")
            provider_button = await bench.tap(f"{litige.CONTEST_PROVIDER}{mission_id}")
            assert provider_button[0].text == get_message("wa_mission_unknown", "fr")
            assert _offers(bench.main) == [] and _notifications(bench.main, "dispute_contested:") == 0

    run(scenario)
