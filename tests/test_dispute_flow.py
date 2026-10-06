"""Litiges, du motif du client à la décision admin, contre le vrai registre.

Le litige s'ouvre dans le registre du backend, qui gèle les fonds ; seule une
décision admin les libère (remboursement total, paiement du prestataire, ou
partage du net). db.py ne fait que recopier l'état renvoyé (CONCEPTION_ARGENT.md).
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import httpx

import db
from messages import get_message
from telegram_bot import admin, payment

CLIENT_ID = 100
PROVIDER_ID = 200
ADMIN_ID = 999


class SentMessage:
    def __init__(self, chat_id, text, **kwargs):
        self.chat_id = chat_id
        self.text = text


class DummyBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(SentMessage(chat_id, text, **kwargs))


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None
        self.edited_markup = None

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text
        self.edited_markup = reply_markup

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text


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
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


class DummyMessage:
    def __init__(self, telegram_id, text="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.text = text
        self.bot = bot or DummyBot()
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append(text)


class DummyState:
    def __init__(self, data=None):
        self._data = data or {}
        self.cleared = False
        self.state = None

    async def get_data(self):
        return self._data

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.cleared = True
        self._data = {}


async def _async_return(value):
    return value


def _languages(monkeypatch):
    for module in (payment, admin):
        monkeypatch.setattr(module, "get_user_language", lambda tid: _async_return("fr"))
        monkeypatch.setattr(module, "get_provider_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(admin, "ADMIN_TELEGRAM_ID", str(ADMIN_ID))


def _paid_mission(tmp_path, monkeypatch, amount=100.0):
    """Mission payée en escrow par le vrai parcours : devis accepté dans db.py,
    paiement Mobile Money par le registre."""
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    _languages(monkeypatch)
    db.create_user(CLIENT_ID, "+243800000100", "Cliente", language="fr")
    db.create_provider(PROVIDER_ID, "+243800000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(CLIENT_ID, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "Fuite d'eau", "urgent": False,
    })
    quote_id = db.create_quote(mission_id, PROVIDER_ID, amount, "USD", 4, "")
    db.accept_quote(quote_id, CLIENT_ID)
    callback = DummyCallback(CLIENT_ID, data=f"pay_mm_{quote_id}_mpesa")
    asyncio.run(payment.paiement_mobile_money_operateur(callback))
    assert db.get_mission_by_id(mission_id)["payment_status"] == "paid_escrow", callback.answered
    return mission_id


def _open_dispute(mission_id, reason="Travail non terminé"):
    state = DummyState({"dispute_mission_id": mission_id})
    message = DummyMessage(CLIENT_ID, text=reason)
    asyncio.run(payment.litige_motif_recu(message, state))
    return message, state


def _go_offline(monkeypatch):
    """Le backend tombe : toute connexion est refusée."""

    def refuse(request):
        raise httpx.ConnectError("backend coupé", request=request)

    class Offline(httpx._client.AsyncClient):
        def __init__(self, *args, **kwargs):
            kwargs["transport"] = httpx.MockTransport(refuse)
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", Offline)


# --- Ouverture -------------------------------------------------------------------


def test_client_signale_probleme_starts_dispute_fsm(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    state = DummyState()
    callback = DummyCallback(CLIENT_ID, data=f"client_report_issue_{mission_id}")

    asyncio.run(payment.client_signale_probleme(callback, state))

    assert state.state == payment.DisputeFlow.reason
    assert state._data["dispute_mission_id"] == mission_id


def test_dispute_freezes_funds_in_the_registry_and_notifies_the_provider(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)

    message, state = _open_dispute(mission_id)

    assert state.cleared
    assert live_backend.mission(mission_id).status == "disputed"
    local = db.get_mission_by_id(mission_id)
    assert local["status"] == "disputed"
    assert local["dispute_reason"] == "Travail non terminé"
    assert local["dispute_deadline"]
    assert message.bot.messages[0].chat_id == PROVIDER_ID
    assert db.get_disputed_missions()[0]["id"] == mission_id


def test_empty_reason_is_refused_without_touching_the_registry(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)

    message, state = _open_dispute(mission_id, reason="   ")

    assert live_backend.mission(mission_id).status == "confirmed"
    assert not state.cleared
    assert message.answers == [get_message("dispute_reason_invalid", "fr")]


def test_dispute_is_not_opened_while_the_backend_is_down_and_the_reason_is_kept(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _go_offline(monkeypatch)

    message, state = _open_dispute(mission_id)

    assert message.answers == [get_message("money_backend_unavailable", "fr")]
    assert not state.cleared
    assert db.get_mission_by_id(mission_id)["status"] == "confirmed"


def test_dispute_after_release_explains_the_mission_was_already_paid(tmp_path, monkeypatch, live_backend):
    """Délai de 24 h dépassé : le backend a libéré seul. db.py l'apprend au
    refus du litige et recopie l'état réel."""
    mission_id = _paid_mission(tmp_path, monkeypatch)
    asyncio.run(payment.prestataire_demarre_mission(DummyCallback(PROVIDER_ID, data=f"mission_start_{mission_id}")))
    asyncio.run(payment.prestataire_termine_mission(DummyCallback(PROVIDER_ID, data=f"mission_finish_{mission_id}")))
    live_backend.age_status(mission_id, hours=25)
    live_backend.auto_release(mission_id)

    message, state = _open_dispute(mission_id)

    assert message.answers == [get_message("dispute_already_released", "fr", mission_id=mission_id)]
    assert state.cleared
    local = db.get_mission_by_id(mission_id)
    assert (local["status"], local["payment_status"]) == ("completed", "released")
    assert live_backend.balance(PROVIDER_ID) == 90.0


def test_another_client_cannot_open_the_dispute(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    state = DummyState({"dispute_mission_id": mission_id})
    message = DummyMessage(555, text="Je conteste")

    asyncio.run(payment.litige_motif_recu(message, state))

    assert message.answers == [get_message("money_error_not_mission_client", "fr")]
    assert live_backend.mission(mission_id).status == "confirmed"


# --- Décision admin -----------------------------------------------------------------


def test_admin_screens_are_closed_when_no_admin_is_configured(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    monkeypatch.setattr(admin, "ADMIN_TELEGRAM_ID", None)

    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(callback))

    assert callback.answered == "Accès admin refusé."
    assert live_backend.mission(mission_id).status == "disputed"


def test_only_the_configured_admin_can_decide(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)

    callback = DummyCallback(CLIENT_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(callback))

    assert callback.answered == "Accès admin refusé."
    assert live_backend.balance(CLIENT_ID) == 0.0


def test_admin_refund_returns_everything_to_the_client_wallet(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    bot = DummyBot()

    asyncio.run(admin.admin_litige_rembourser(DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}", bot=bot)))

    assert live_backend.balance(CLIENT_ID) == 100.0
    assert live_backend.balance(PROVIDER_ID) == 0.0
    local = db.get_mission_by_id(mission_id)
    assert (local["status"], local["payment_status"]) == ("cancelled", "refunded")
    assert {message.chat_id for message in bot.messages} == {CLIENT_ID, PROVIDER_ID}
    assert db.get_disputed_missions() == []


def test_admin_release_pays_the_provider_net(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    bot = DummyBot()

    asyncio.run(admin.admin_litige_payer_prestataire(DummyCallback(ADMIN_ID, data=f"admin_dispute_release_{mission_id}", bot=bot)))

    assert live_backend.balance(PROVIDER_ID) == 90.0
    assert live_backend.balance(CLIENT_ID) == 0.0
    provider_message = next(message for message in bot.messages if message.chat_id == PROVIDER_ID)
    assert "90.00" in provider_message.text


def test_admin_split_starts_fsm(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    state = DummyState()
    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_split_{mission_id}")

    asyncio.run(admin.admin_litige_demarrer_partage(callback, state))

    assert state.state == admin.AdminDisputeSplit.percentage
    assert "net prestataire" in callback.message.edited_text


def test_admin_split_shares_the_provider_net_and_keeps_the_commission(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    bot = DummyBot()
    message = DummyMessage(ADMIN_ID, text="50", bot=bot)
    state = DummyState({"dispute_split_mission_id": mission_id})

    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert state.cleared
    assert live_backend.balance(PROVIDER_ID) == 45.0
    assert live_backend.balance(CLIENT_ID) == 45.0
    assert "45.00 USD au prestataire" in message.answers[0]
    assert "10.00 USD de commission" in message.answers[0]
    local = db.get_mission_by_id(mission_id)
    assert (local["status"], local["payment_status"]) == ("completed", "split")
    client_message = next(sent for sent in bot.messages if sent.chat_id == CLIENT_ID)
    assert "45.00" in client_message.text


def test_admin_split_rejects_non_numeric_input_without_crashing(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    message = DummyMessage(ADMIN_ID, text="moitié")
    state = DummyState({"dispute_split_mission_id": mission_id})

    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert not state.cleared
    assert live_backend.mission(mission_id).status == "disputed"


def test_admin_split_refuses_an_out_of_range_percentage(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    message = DummyMessage(ADMIN_ID, text="150")
    state = DummyState({"dispute_split_mission_id": mission_id})

    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert message.answers == [get_message("money_error_generic", "fr")]
    assert live_backend.mission(mission_id).status == "disputed"


def test_admin_decision_is_refused_while_the_backend_is_down(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    _go_offline(monkeypatch)

    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(callback))
    message = DummyMessage(ADMIN_ID, text="50")
    state = DummyState({"dispute_split_mission_id": mission_id})
    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert callback.answered == get_message("money_backend_unavailable", "fr")
    assert message.answers == [get_message("money_backend_unavailable", "fr")]
    assert not state.cleared  # l'admin renvoie le même pourcentage
    assert db.get_mission_by_id(mission_id)["status"] == "disputed"


def test_a_dispute_is_decided_once(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)
    asyncio.run(admin.admin_litige_rembourser(DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")))

    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_release_{mission_id}")
    asyncio.run(admin.admin_litige_payer_prestataire(callback))

    assert callback.answered == get_message("money_error_already_settled", "fr")
    assert live_backend.balance(CLIENT_ID) == 100.0
    assert live_backend.balance(PROVIDER_ID) == 0.0


def test_confirming_a_disputed_mission_is_refused(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch)
    _open_dispute(mission_id)

    callback = DummyCallback(CLIENT_ID, data=f"client_confirm_done_{mission_id}")
    asyncio.run(payment.client_confirme_mission_terminee(callback, DummyState()))

    assert callback.answered == get_message("money_error_mission_disputed", "fr")
    assert live_backend.balance(PROVIDER_ID) == 0.0
