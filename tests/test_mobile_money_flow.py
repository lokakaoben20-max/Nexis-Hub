"""Parcours Mobile Money du bot contre le vrai backend (fixture live_backend) :
paiement par intention confirmée par l'agrégateur, retrait validé par l'admin."""

import asyncio

from backend.app import mobile_money
from backend.app.payment_gateway import PENDING, SUCCEEDED, GatewayResult
from messages import get_message
from telegram_bot import admin, dashboard, payment
from tests.test_dispute_flow import (
    ADMIN_ID,
    CLIENT_ID,
    PROVIDER_ID,
    DummyBot,
    DummyCallback,
    DummyMessage,
    DummyState,
    _async_return,
    _paid_mission,
)

import db


class SlowGateway(mobile_money.get_gateway().__class__):
    """Agrégateur simulé qui répond « en attente » tant qu'on ne lui dit pas
    que le client a validé sur son téléphone."""

    validated = False

    def collection_status(self, intent):
        if not SlowGateway.validated:
            return GatewayResult(PENDING, f"SLOW-{intent.id}")
        return GatewayResult(SUCCEEDED, f"SLOW-{intent.id}", intent.amount, intent.currency, 0)


def _accepted_quote(tmp_path, monkeypatch):
    """Mission avec devis accepté, pas encore payée (même jeu que _paid_mission)."""
    from tests.test_dispute_flow import _languages

    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    _languages(monkeypatch)
    for module in (dashboard,):
        monkeypatch.setattr(module, "get_user_language", lambda tid: _async_return("fr"))
        monkeypatch.setattr(module, "get_provider_language", lambda tid: _async_return("fr"))
    db.create_user(CLIENT_ID, "0810000100", "Cliente", language="fr")
    db.create_provider(PROVIDER_ID, "+243970000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(CLIENT_ID, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD", "description": "Fuite", "urgent": False,
    })
    quote_id = db.create_quote(mission_id, PROVIDER_ID, 100.0, "USD", 4, "")
    db.accept_quote(quote_id, CLIENT_ID)
    return mission_id, quote_id


def test_mobile_money_asks_the_operator_with_the_detected_one_first(tmp_path, monkeypatch, live_backend):
    _, quote_id = _accepted_quote(tmp_path, monkeypatch)
    callback = DummyCallback(CLIENT_ID, data=f"pay_mobile_{quote_id}")

    asyncio.run(payment.paiement_mobile_money(callback))

    assert "+243810000100" in callback.message.edited_text  # 0810… normalisé
    assert callback.message.edited_markup.inline_keyboard[0][0].callback_data == f"pay_mm_{quote_id}_mpesa"


def test_a_payment_waits_for_the_phone_then_the_backend_confirms_and_notifies(tmp_path, monkeypatch, live_backend):
    SlowGateway.validated = False
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: SlowGateway())
    mission_id, quote_id = _accepted_quote(tmp_path, monkeypatch)

    callback = DummyCallback(CLIENT_ID, data=f"pay_mm_{quote_id}_mpesa")
    asyncio.run(payment.paiement_mobile_money_operateur(callback))
    assert "téléphone" in callback.message.edited_text
    assert live_backend.mission(mission_id).payment_status is None  # rien de payé

    SlowGateway.validated = True  # le client a tapé son code secret
    intent_id = int(callback.message.edited_markup.inline_keyboard[0][0].callback_data.removeprefix("check_mm_"))
    check = DummyCallback(CLIENT_ID, data=f"check_mm_{intent_id}")
    asyncio.run(payment.verifier_paiement_mobile_money(check))

    assert live_backend.mission(mission_id).payment_status == "paid_escrow"
    assert db.get_mission_by_id(mission_id)["payment_status"] == "paid_escrow"
    assert "SLOW-" in check.message.edited_text
    # Le backend a prévenu client et prestataire ; le bot n'envoie rien en double.
    assert {chat_id for chat_id, _ in live_backend.sent} == {CLIENT_ID, PROVIDER_ID}
    assert check.bot.messages == []


def test_only_the_client_can_check_their_payment(tmp_path, monkeypatch, live_backend):
    SlowGateway.validated = False
    monkeypatch.setattr(mobile_money, "get_gateway", lambda: SlowGateway())
    _, quote_id = _accepted_quote(tmp_path, monkeypatch)
    callback = DummyCallback(CLIENT_ID, data=f"pay_mm_{quote_id}_mpesa")
    asyncio.run(payment.paiement_mobile_money_operateur(callback))
    intent_id = int(callback.message.edited_markup.inline_keyboard[0][0].callback_data.removeprefix("check_mm_"))

    intruder = DummyCallback(999, data=f"check_mm_{intent_id}")
    asyncio.run(payment.verifier_paiement_mobile_money(intruder))

    assert intruder.answered == get_message("money_error_not_mission_client", "fr")


def _earned(tmp_path, monkeypatch):
    """Le prestataire a gagné 90 USD (mission payée, faite, confirmée)."""
    mission_id = _paid_mission(tmp_path, monkeypatch)
    for module in (dashboard,):
        monkeypatch.setattr(module, "get_user_language", lambda tid: _async_return("fr"))
        monkeypatch.setattr(module, "get_provider_language", lambda tid: _async_return("fr"))
    asyncio.run(payment.prestataire_demarre_mission(DummyCallback(PROVIDER_ID, data=f"mission_start_{mission_id}")))
    asyncio.run(payment.prestataire_termine_mission(DummyCallback(PROVIDER_ID, data=f"mission_finish_{mission_id}")))
    asyncio.run(payment.client_confirme_mission_terminee(DummyCallback(CLIENT_ID, data=f"client_confirm_done_{mission_id}"), DummyState()))


def _withdraw(amount_text="50"):
    state = DummyState()
    asyncio.run(dashboard.retrait_choisir_devise(DummyCallback(PROVIDER_ID, data="wallet_withdraw"), state))
    asyncio.run(dashboard.retrait_demander_montant(DummyCallback(PROVIDER_ID, data="wd_cur_USD"), state))
    message = DummyMessage(PROVIDER_ID, text=amount_text)
    asyncio.run(dashboard.retrait_montant_recu(message, state))
    final = DummyCallback(PROVIDER_ID, data="wd_op_orange")
    asyncio.run(dashboard.retrait_operateur_recu(final, state))
    return message, final, state


def test_a_withdrawal_is_reserved_then_sent_after_admin_approval(tmp_path, monkeypatch, live_backend):
    _earned(tmp_path, monkeypatch)

    message, final, state = _withdraw("50")
    assert state.cleared
    assert "validation" in final.message.edited_text
    assert live_backend.balance(PROVIDER_ID) == 40.0  # 50 réservés

    listing = DummyCallback(ADMIN_ID, data="admin_payouts")
    asyncio.run(admin.admin_payouts(listing))
    payout_line = listing.message.edited_text
    assert payout_line is not None

    bot = DummyBot()
    asyncio.run(admin.admin_decider_retrait(DummyCallback(ADMIN_ID, data="admin_payout_ok_1", bot=bot)))
    assert live_backend.balance(PROVIDER_ID) == 40.0
    assert bot.messages[0].chat_id == PROVIDER_ID
    assert "envoyé" in bot.messages[0].text


def test_a_rejected_withdrawal_gives_the_money_back(tmp_path, monkeypatch, live_backend):
    _earned(tmp_path, monkeypatch)
    _withdraw("50")

    bot = DummyBot()
    asyncio.run(admin.admin_decider_retrait(DummyCallback(ADMIN_ID, data="admin_payout_no_1", bot=bot)))

    assert live_backend.balance(PROVIDER_ID) == 90.0
    assert "revenu" in bot.messages[0].text


def test_withdrawal_amount_is_checked_by_the_backend(tmp_path, monkeypatch, live_backend):
    _earned(tmp_path, monkeypatch)

    _, final, _ = _withdraw("500")
    assert final.message.edited_text == get_message("money_error_insufficient_balance", "fr")
    _, final, _ = _withdraw("2")
    assert final.message.edited_text == get_message("money_error_below_minimum", "fr")
    assert live_backend.balance(PROVIDER_ID) == 90.0


def test_only_the_admin_sees_and_decides_withdrawals(tmp_path, monkeypatch, live_backend):
    _earned(tmp_path, monkeypatch)
    _withdraw("50")

    callback = DummyCallback(PROVIDER_ID, data="admin_payout_ok_1")
    asyncio.run(admin.admin_decider_retrait(callback))

    assert callback.answered == "Accès admin refusé."
    assert live_backend.balance(PROVIDER_ID) == 40.0
