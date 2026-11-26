"""Service WhatsApp, étape 6 (seconde partie) : payer une demande.

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis) ; agrégateur Mobile Money de test (backend/tests/test_mobile_money.py).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from backend.tests.test_mobile_money import FakeGateway
from messages import get_message
from whatsapp_bot import devis, paiement
from whatsapp_bot.tests.conftest import provider_quote, publish_terms, run, verified_provider
from whatsapp_bot.tests.test_whatsapp_demande import _choices, _up_to_recap
from whatsapp_bot.tests.test_whatsapp_devis import _mission

pytestmark = pytest.mark.conditions_reelles

OTHER_BSUID = "CD.2000000000000000002"


@pytest.fixture
def gateway(backend_main, monkeypatch):
    from backend.app import mobile_money

    fake = FakeGateway()
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: fake)
    return fake


def _credit(main, amount, currency="USD"):
    from backend.app import ledger

    with main.database.SessionLocal() as db:
        account_id = _mission(main).client_account_id
        ledger.record_opening_balance(db, account_id, currency, amount)
        db.commit()


def _fundings(main):
    from backend.app.ledger import FUNDING, MoneyOperation

    with main.database.SessionLocal() as db:
        return [(row.kind, row.reference) for row in db.execute(select(MoneyOperation).filter_by(phase=FUNDING)).scalars()]


def _intents(main):
    from backend.app.models import PaymentIntent

    with main.database.SessionLocal() as db:
        return [(row.id, row.status, row.phone, row.operator) for row in db.execute(select(PaymentIntent)).scalars()]


async def _accepted(bench, amount=40, currency="USD", language="fr"):
    """Demande WhatsApp, devis d'un prestataire Telegram, accepté : rend ce
    que le service a répondu à l'acceptation et le numéro du devis."""
    await bench.register(language=language)
    await _up_to_recap(bench, currency=currency)
    await bench.tap("m:confirm")
    quote_id = provider_quote(bench.main, _mission(bench.main).mission_id, amount=amount, currency=currency)
    return await bench.tap(f"quote_accept_{quote_id}"), quote_id


def test_accepting_a_quote_offers_to_pay_and_the_wallet_only_when_it_is_enough(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            accepted, quote_id = await _accepted(bench)
            assert accepted[0].text.startswith("✅")
            card = accepted[-1]
            assert card.kind == "button" and "NXH-0001" in card.text and "40.00 USD" in card.text
            assert _choices([card]) == [f"{paiement.PAY_MOBILE}{quote_id}", paiement.PAY_LATER]
            _credit(bench.main, 100)
            shown = await bench.tap(f"mis:{_mission(bench.main).mission_id}")
            card = [message for message in shown if message.kind == "button"][-1]
            assert _choices([card]) == [f"{paiement.PAY_MOBILE}{quote_id}", f"{paiement.PAY_WALLET}{quote_id}", paiement.PAY_LATER]
            assert "100.00 USD" in card.text
            later = await bench.tap(paiement.PAY_LATER)
            assert later[-1].kind == "list"  # menu

    run(scenario)


def test_paying_with_the_wallet_debits_once_even_on_a_double_tap(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            _credit(bench.main, 100)
            first = await bench.tap(f"{paiement.PAY_WALLET}{quote_id}")
            assert first[0].text.startswith("✅") and "40.00 USD" in first[0].text and "NXH-0001" in first[0].text
            again = await bench.tap(f"{paiement.PAY_WALLET}{quote_id}")
            assert again[0].text == first[0].text  # même paiement, même référence
            assert _fundings(bench.main) == [("fund_wallet", f"WLT-{quote_id:04d}")]
            assert _mission(bench.main).payment_status == "paid_escrow"
            shown = await bench.tap(f"mis:{_mission(bench.main).mission_id}")
            assert get_message("wa_status_confirmed_paid", "fr") in shown[0].text
            assert not [message for message in shown if message.kind == "button"]

    run(scenario)


def test_a_replayed_wallet_payment_after_a_lost_answer_pays_once(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            _credit(bench.main, 100)
            payload = bench.fake.choice_message(f"{paiement.PAY_WALLET}{quote_id}")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500
            assert (await bench.post(payload)).status_code == 200
            assert bench.fake.sent[-2].text.startswith("✅")

    run(scenario)
    assert len(_fundings(bench.main)) == 1


def test_not_enough_in_the_wallet_says_so_and_moves_nothing(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            _credit(bench.main, 10)
            # Un ancien bouton « Portefeuille » (solde dépensé depuis).
            refused = await bench.tap(f"{paiement.PAY_WALLET}{quote_id}")
            assert refused[0].text == get_message("wa_pay_insufficient", "fr")
            assert _fundings(bench.main) == []

    run(scenario)


def test_paying_with_mobile_money_uses_the_whatsapp_number_and_waits_for_the_aggregator(bench, gateway):
    verified_provider(bench.main)
    gateway.collection = "pending"

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            operators = await bench.tap(f"{paiement.PAY_MOBILE}{quote_id}")
            assert "+243810000001" in operators[0].text and "40.00 USD" in operators[0].text
            # Le numéro commence par 81 : M-Pesa en premier.
            assert _choices(operators) == [f"{paiement.PAY_OPERATOR}{quote_id}:{op}" for op in ("mpesa", "airtel", "orange")]
            waiting = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            ((intent_id, status, phone, operator),) = _intents(bench.main)
            assert (status, phone, operator) == ("pending", "+243810000001", "mpesa")
            assert waiting[0].text == get_message("wa_pay_pending", "fr", amount="40.00", currency="USD")
            assert _choices(waiting) == [f"{paiement.PAY_CHECK}{intent_id}"]
            still = await bench.tap(f"{paiement.PAY_CHECK}{intent_id}")
            assert _choices(still) == [f"{paiement.PAY_CHECK}{intent_id}"]
            assert _fundings(bench.main) == []
            # L'agrégateur confirme (webhook, ou vérification de secours).
            from backend.app import mobile_money

            gateway.collection = "succeeded"
            with bench.main.database.SessionLocal() as db:
                mobile_money.refresh_intent(db, intent_id)
            done = await bench.tap(f"{paiement.PAY_CHECK}{intent_id}")
            assert done[0].text.startswith("✅") and "40.00 USD" in done[0].text
            assert _mission(bench.main).payment_status == "paid_escrow"

    run(scenario)


def test_a_double_tap_on_the_operator_sends_one_request_to_the_phone(bench, gateway):
    verified_provider(bench.main)
    gateway.collection = "pending"

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            payload = bench.fake.choice_message(f"{paiement.PAY_OPERATOR}{quote_id}:airtel")
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500
            assert (await bench.post(payload)).status_code == 200

    run(scenario)
    assert len(_intents(bench.main)) == 1 and len(gateway.known) == 1


def test_a_refused_payment_says_nothing_was_charged(bench, gateway):
    verified_provider(bench.main)
    gateway.collection = "failed"

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            failed = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert failed[0].text == get_message("wa_pay_failed", "fr", reference="NXH-0001")
            # La demande se paie encore : sa carte « Payer » est là.
            shown = await bench.tap(f"mis:{_mission(bench.main).mission_id}")
            assert f"{paiement.PAY_MOBILE}{quote_id}" in _choices(shown)

    run(scenario)


def test_a_different_amount_is_not_a_payment(bench, gateway):
    verified_provider(bench.main)
    gateway.amount = "39.00"

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            answer = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert answer[0].text == get_message("wa_pay_mismatch", "fr", reference="NXH-0001")
            assert _fundings(bench.main) == []

    run(scenario)


def test_an_unreachable_aggregator_or_backend_charges_nothing_twice(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            gateway.down = True
            unknown = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert unknown[0].text == get_message("wa_pay_unconfirmed", "fr", amount="40.00", currency="USD")
            bench.backend_down = True
            down = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert down[0].text == get_message("service_unavailable", "fr")
            bench.backend_down = False
            again = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert again[0].text == unknown[0].text

    run(scenario)
    assert len(_intents(bench.main)) == 1 and _fundings(bench.main) == []


def test_paused_payments_are_explained(bench, gateway):
    verified_provider(bench.main)
    from backend.app import interrupteurs

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            with bench.main.database.SessionLocal() as db:
                interrupteurs.switch(db, interrupteurs.COLLECTIONS, open=False, reason="test", source="cli")
            paused = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert paused[0].text == get_message("wa_pay_paused", "fr")

    run(scenario)
    assert _intents(bench.main) == []


def test_someone_else_cannot_pay_or_read_the_payment(bench, gateway):
    verified_provider(bench.main)
    gateway.collection = "pending"

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            ((intent_id, *_rest),) = _intents(bench.main)
            other = {"bsuid": OTHER_BSUID, "phone": "243810000002"}
            await bench.register(name="Autre", **other)
            for choice in (f"{paiement.PAY_OPERATOR}{quote_id}:mpesa", f"{paiement.PAY_WALLET}{quote_id}", f"{paiement.PAY_CHECK}{intent_id}"):
                refused = await bench.tap(choice, **other)
                assert refused[0].text == get_message("wa_pay_unknown", "fr")

    run(scenario)
    assert len(_intents(bench.main)) == 1


def test_new_terms_are_accepted_before_paying(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            publish_terms(bench.main, "2026-12-01", at=now, documents=("cgu",))
            asked = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert _choices(asked[-1:]) == [devis.TERMS_ACCEPT, devis.TERMS_DECLINE]
            shown = await bench.tap(devis.TERMS_ACCEPT)
            # La demande est remontrée avec sa carte « Payer » : un nouvel appui paie.
            assert f"{paiement.PAY_MOBILE}{quote_id}" in _choices(shown)
            paid = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa")
            assert paid[0].text.startswith("✅")

    run(scenario)
    assert _intents(bench.main)[0][1] == "succeeded"


def test_a_number_outside_the_drc_or_hidden_cannot_pay_by_mobile_money(bench, gateway):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            _accepted_answer, quote_id = await _accepted(bench)
            # Le numéro est celui qui écrit, donné par Meta avec le message.
            refused = await bench.tap(f"{paiement.PAY_MOBILE}{quote_id}", phone="33612345678")
            assert refused[0].text == get_message("wa_pay_no_phone", "fr")
            hidden = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:mpesa", phone=None)
            assert hidden[0].text == get_message("wa_pay_no_phone", "fr")

    run(scenario)
    assert _intents(bench.main) == []


@pytest.mark.parametrize("lang", ["fr", "ln", "en"])
def test_payment_screens_respect_whatsapp_limits(bench, gateway, lang):
    verified_provider(bench.main)
    gateway.collection = "pending"

    async def scenario():
        async with bench:
            # Le faux Meta refuserait un écran hors limites (réponse 500).
            _accepted_answer, quote_id = await _accepted(bench, amount=1250000, currency="CDF", language=lang)
            _credit(bench.main, 2000000, currency="CDF")
            shown = await bench.tap(f"mis:{_mission(bench.main).mission_id}")
            assert "1 250 000 FC" in [message for message in shown if message.kind == "button"][-1].text
            await bench.tap(f"{paiement.PAY_MOBILE}{quote_id}")
            waiting = await bench.tap(f"{paiement.PAY_OPERATOR}{quote_id}:orange")
            assert waiting[0].kind == "button"

    run(scenario)


def test_numbers_and_operators_are_read_like_on_telegram():
    assert paiement.normalize_phone("0812345678") == "+243812345678"
    assert paiement.normalize_phone("+243 97 123 4567") == "+243971234567"
    assert paiement.normalize_phone("33612345678") is None
    assert [paiement.detect_operator(f"+243{prefix}1234567") for prefix in ("81", "97", "84", "90")] == ["mpesa", "airtel", "orange", None]
