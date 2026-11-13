"""Litiges, du motif du client à la décision admin, contre le vrai registre.

Le litige s'ouvre dans le registre du backend, qui gèle les fonds ; seule une
décision admin les libère (remboursement total, paiement du prestataire, ou
partage du net). db.py n'en garde aucune copie (CONCEPTION_MISSIONS.md).
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
    # Le backend revérifie l'admin (backend/app/main.py::_require_admin).
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", str(ADMIN_ID))


def _paid_mission(tmp_path, monkeypatch, live, amount=100.0):
    """Mission payée en escrow par le vrai parcours : mission et devis accepté
    dans le backend, paiement Mobile Money par le registre."""
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()
    _languages(monkeypatch)
    db.create_user(CLIENT_ID, "+243800000100", "Cliente", language="fr")
    db.create_provider(PROVIDER_ID, "+243800000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id, quote_id = live.accepted_quote(CLIENT_ID, PROVIDER_ID, amount=amount, service="service_plomberie")
    callback = DummyCallback(CLIENT_ID, data=f"qpay_op_{quote_id}_mpesa")
    asyncio.run(payment.paiement_mobile_money_operateur(callback))
    assert live.mission(mission_id).payment_status == "paid_escrow", callback.answered
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
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    state = DummyState()
    callback = DummyCallback(CLIENT_ID, data=f"client_report_issue_{mission_id}")

    asyncio.run(payment.client_signale_probleme(callback, state))

    assert state.state == payment.DisputeFlow.reason
    assert state._data["dispute_mission_id"] == mission_id


def test_dispute_freezes_funds_in_the_registry_and_notifies_the_provider(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)

    message, state = _open_dispute(mission_id)

    assert state.cleared
    assert live_backend.mission(mission_id).status == "disputed"
    stored = live_backend.mission(mission_id)
    assert stored.dispute_reason == "Travail non terminé"
    assert stored.dispute_deadline
    assert message.bot.messages[0].chat_id == PROVIDER_ID
    assert live_backend.disputed_ids() == [mission_id]


def test_empty_reason_is_refused_without_touching_the_registry(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)

    message, state = _open_dispute(mission_id, reason="   ")

    assert live_backend.mission(mission_id).status == "confirmed"
    assert not state.cleared
    assert message.answers == [get_message("dispute_reason_invalid", "fr")]


def test_dispute_is_not_opened_while_the_backend_is_down_and_the_reason_is_kept(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _go_offline(monkeypatch)

    message, state = _open_dispute(mission_id)

    assert message.answers == [get_message("money_backend_unavailable", "fr")]
    assert not state.cleared
    assert live_backend.mission(mission_id).status == "confirmed"


def test_dispute_after_release_explains_the_mission_was_already_paid(tmp_path, monkeypatch, live_backend):
    """Délai de 48 h dépassé : le backend a libéré seul ; le litige refusé
    l'explique au client."""
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    asyncio.run(payment.prestataire_demarre_mission(DummyCallback(PROVIDER_ID, data=f"mission_start_{mission_id}")))
    asyncio.run(payment.prestataire_termine_mission(DummyCallback(PROVIDER_ID, data=f"mission_finish_{mission_id}")))
    live_backend.age_status(mission_id, hours=48)
    live_backend.auto_release(mission_id)

    message, state = _open_dispute(mission_id)

    assert message.answers == [get_message("dispute_already_released", "fr", mission_id=mission_id)]
    assert state.cleared
    local = live_backend.mission(mission_id)
    assert (local.status, local.payment_status) == ("completed", "released")
    assert live_backend.balance(PROVIDER_ID) == 90.0


def test_another_client_cannot_open_the_dispute(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    state = DummyState({"dispute_mission_id": mission_id})
    message = DummyMessage(555, text="Je conteste")

    asyncio.run(payment.litige_motif_recu(message, state))

    assert message.answers == [get_message("money_error_not_mission_client", "fr")]
    assert live_backend.mission(mission_id).status == "confirmed"


# --- Décision admin -----------------------------------------------------------------


def test_admin_screens_are_closed_when_no_admin_is_configured(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    monkeypatch.setattr(admin, "ADMIN_TELEGRAM_ID", None)

    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(callback))

    assert callback.answered == "Accès admin refusé."
    assert live_backend.mission(mission_id).status == "disputed"


def test_only_the_configured_admin_can_decide(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)

    callback = DummyCallback(CLIENT_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(callback))

    assert callback.answered == "Accès admin refusé."
    assert live_backend.balance(CLIENT_ID) == 0.0


OTHER_ADMIN_ID = 998


def _execute_when_due(live, mission_id):
    """La tâche du planificateur passe à la fin du délai de contestation."""
    from backend.app import ledger, tasks

    with live.database.SessionLocal() as session:
        execute_after = ledger.dispute_decisions(session, mission_id)[0].execute_after
    return tasks.execute_due_dispute_decisions(execute_after)


def _first_decision(live, mission_id):
    from backend.app import ledger

    with live.database.SessionLocal() as session:
        return ledger.dispute_decisions(session, mission_id)[0]


def _become_admin(monkeypatch, telegram_id):
    monkeypatch.setattr(admin, "ADMIN_TELEGRAM_ID", str(telegram_id))
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", str(telegram_id))


def test_admin_refund_is_recorded_then_executed_after_three_days(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")

    asyncio.run(admin.admin_litige_rembourser(callback))

    assert "décision enregistrée" in callback.message.edited_text
    assert "100.00 USD au client" in callback.message.edited_text
    # Rien ne bouge pendant le délai de contestation.
    assert live_backend.balance(CLIENT_ID) == 0.0
    assert live_backend.mission(mission_id).status == "disputed"
    # Le backend prévient le client et le prestataire, avec la date d'exécution.
    assert {chat_id for chat_id, _ in live_backend.sent} == {CLIENT_ID, PROVIDER_ID}
    client_notice = next(text for chat_id, text in live_backend.sent if chat_id == CLIENT_ID)
    assert "Remboursé à vous : <b>100.00 USD</b>" in client_notice

    live_backend.sent.clear()
    assert _execute_when_due(live_backend, mission_id) == 1

    assert live_backend.balance(CLIENT_ID) == 100.0
    assert live_backend.balance(PROVIDER_ID) == 0.0
    local = live_backend.mission(mission_id)
    assert (local.status, local.payment_status) == ("cancelled", "refunded")
    assert {chat_id for chat_id, _ in live_backend.sent} == {CLIENT_ID, PROVIDER_ID}
    assert live_backend.disputed_ids() == []


def test_admin_release_pays_the_provider_net_after_three_days(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)

    asyncio.run(admin.admin_litige_payer_prestataire(DummyCallback(ADMIN_ID, data=f"admin_dispute_release_{mission_id}")))
    assert live_backend.balance(PROVIDER_ID) == 0.0
    live_backend.sent.clear()
    _execute_when_due(live_backend, mission_id)

    assert live_backend.balance(PROVIDER_ID) == 90.0
    assert live_backend.balance(CLIENT_ID) == 0.0
    provider_message = next(text for chat_id, text in live_backend.sent if chat_id == PROVIDER_ID)
    assert "90.00" in provider_message


def test_admin_split_starts_fsm(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    state = DummyState()
    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_split_{mission_id}")

    asyncio.run(admin.admin_litige_demarrer_partage(callback, state))

    assert state.state == admin.AdminDisputeSplit.percentage
    assert "le client récupère le reste" in callback.message.edited_text


def test_admin_split_is_prorata_commission_included(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    message = DummyMessage(ADMIN_ID, text="50")
    state = DummyState({"dispute_split_mission_id": mission_id})

    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert state.cleared
    assert "45.00 USD au prestataire" in message.answers[0]
    assert "50.00 USD au client" in message.answers[0]
    assert "5.00 USD de commission" in message.answers[0]
    assert live_backend.balance(PROVIDER_ID) == 0.0

    live_backend.sent.clear()
    _execute_when_due(live_backend, mission_id)

    assert live_backend.balance(PROVIDER_ID) == 45.0
    assert live_backend.balance(CLIENT_ID) == 50.0
    local = live_backend.mission(mission_id)
    assert (local.status, local.payment_status) == ("completed", "split")
    client_message = next(text for chat_id, text in live_backend.sent if chat_id == CLIENT_ID)
    assert "50.00" in client_message


def test_admin_split_rejects_non_numeric_input_without_crashing(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    message = DummyMessage(ADMIN_ID, text="moitié")
    state = DummyState({"dispute_split_mission_id": mission_id})

    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert not state.cleared
    assert live_backend.mission(mission_id).status == "disputed"


def test_admin_split_refuses_an_out_of_range_percentage(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    message = DummyMessage(ADMIN_ID, text="150")
    state = DummyState({"dispute_split_mission_id": mission_id})

    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert message.answers == [get_message("money_error_generic", "fr")]
    assert live_backend.mission(mission_id).status == "disputed"


def test_admin_decision_is_refused_while_the_backend_is_down(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
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
    assert live_backend.mission(mission_id).status == "disputed"


def test_a_dispute_is_decided_once(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    asyncio.run(admin.admin_litige_rembourser(DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")))

    callback = DummyCallback(ADMIN_ID, data=f"admin_dispute_release_{mission_id}")
    asyncio.run(admin.admin_litige_payer_prestataire(callback))

    assert callback.answered == get_message("money_error_decision_pending", "fr")
    assert _first_decision(live_backend, mission_id).decision == "refund"


# --- Contestation et révision -----------------------------------------------------


def _contest(telegram_id, role, mission_id, reason="Le travail n'est pas fini"):
    state = DummyState()
    callback = DummyCallback(telegram_id, data=f"dispute_contest_{role}_{mission_id}")
    asyncio.run(payment.contester_decision(callback, state))
    assert state.state == payment.DisputeContestFlow.reason
    message = DummyMessage(telegram_id, text=reason)
    asyncio.run(payment.contestation_motif_recu(message, state))
    return message, state


def test_the_provider_contests_and_the_money_stays_frozen(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    asyncio.run(admin.admin_litige_rembourser(DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")))
    from backend.app import tasks

    monkeypatch.setattr(tasks, "ADMIN_TELEGRAM_ID", str(ADMIN_ID))
    live_backend.sent.clear()

    message, state = _contest(PROVIDER_ID, "p", mission_id)

    assert state.cleared
    assert message.answers == [get_message("dispute_contest_sent", "fr", mission_id=mission_id)]
    decision = _first_decision(live_backend, mission_id)
    assert (decision.contested_by_role, decision.contest_reason) == ("provider", "Le travail n'est pas fini")
    # Le client et l'admin sont prévenus ; la tâche n'exécute plus rien.
    assert {chat_id for chat_id, _ in live_backend.sent} == {CLIENT_ID, ADMIN_ID}
    assert _execute_when_due(live_backend, mission_id) == 0
    assert live_backend.balance(CLIENT_ID) == 0.0


def test_only_the_parties_can_contest(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    asyncio.run(admin.admin_litige_rembourser(DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")))

    message, state = _contest(555, "c", mission_id)

    assert message.answers == [get_message("money_error_not_mission_party", "fr")]
    assert _first_decision(live_backend, mission_id).contested_at is None


def test_contest_is_kept_while_the_backend_is_down(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    asyncio.run(admin.admin_litige_rembourser(DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")))
    _go_offline(monkeypatch)

    message, state = _contest(CLIENT_ID, "c", mission_id)

    assert message.answers == [get_message("money_backend_unavailable", "fr")]
    assert not state.cleared


def test_the_review_is_done_by_another_admin_and_applied_at_once(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)
    asyncio.run(admin.admin_litige_payer_prestataire(DummyCallback(ADMIN_ID, data=f"admin_dispute_release_{mission_id}")))
    _contest(CLIENT_ID, "c", mission_id)

    same = DummyCallback(ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(same))
    assert same.answered == get_message("money_error_same_reviewer", "fr")
    assert live_backend.balance(CLIENT_ID) == 0.0

    _become_admin(monkeypatch, OTHER_ADMIN_ID)
    live_backend.sent.clear()
    other = DummyCallback(OTHER_ADMIN_ID, data=f"admin_dispute_refund_{mission_id}")
    asyncio.run(admin.admin_litige_rembourser(other))

    assert "révision appliquée" in other.message.edited_text
    assert live_backend.balance(CLIENT_ID) == 100.0
    assert live_backend.mission(mission_id).payment_status == "refunded"
    assert {chat_id for chat_id, _ in live_backend.sent} == {CLIENT_ID, PROVIDER_ID}


def test_confirming_a_disputed_mission_is_refused(tmp_path, monkeypatch, live_backend):
    mission_id = _paid_mission(tmp_path, monkeypatch, live_backend)
    _open_dispute(mission_id)

    callback = DummyCallback(CLIENT_ID, data=f"client_confirm_done_{mission_id}")
    asyncio.run(payment.client_confirme_mission_terminee(callback, DummyState()))

    assert callback.answered == get_message("money_error_mission_disputed", "fr")
    assert live_backend.balance(PROVIDER_ID) == 0.0
