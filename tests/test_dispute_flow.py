"""Système de litiges : motif client -> statut réel + gel de l'escrow -> résolution admin.

Le schéma (dispute_reason, dispute_deadline) et l'écran admin_disputes existaient déjà
mais rien ne posait jamais status='disputed' ni ne proposait d'action de résolution
(trouvaille du balayage db.py/backend, voir AGENTS.md). Couvre : ouverture du litige
(motif requis, gel de release_payment), et les deux résolutions admin (rembourser le
client / payer le prestataire), avec double écriture backend best-effort comme le
reste du projet.
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

import db
from telegram_bot import admin, backend_client, payment


class DummyResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyAsyncClient:
    last_request = None

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, json=None):
        DummyAsyncClient.last_request = {"url": url, "json": json}
        return DummyResponse({"status": "ok"})

    async def get(self, url, params=None):
        return DummyResponse({"client": None, "provider": None})


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

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

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


def _init_db(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()


def _use_dummy_backend(monkeypatch):
    DummyAsyncClient.last_request = None
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


def _setup_paid_mission(tmp_path, monkeypatch, client_id=100, provider_id=200, amount=100.0):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(client_id, "+243800000100", "Cliente", language="fr")
    db.create_provider(provider_id, "+243800000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(client_id, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "Fuite d'eau", "urgent": False,
    })
    quote_id = db.create_quote(mission_id, provider_id, amount, "USD", 4, "")
    db.accept_quote(quote_id, client_id)
    db.mark_quote_paid(quote_id, client_id, operator="mobile_money_simulation")
    return mission_id


# --- db.py : cycle de vie du litige ----------------------------------------


def test_open_dispute_sets_status_reason_and_deadline(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)

    mission = db.open_dispute(mission_id, 100, "Le prestataire n'est jamais venu")

    assert mission["status"] == "disputed"
    assert mission["dispute_reason"] == "Le prestataire n'est jamais venu"
    assert mission["dispute_deadline"], "une deadline doit être posée"
    assert mission["payment_status"] == "paid_escrow", "l'argent reste en escrow, pas touché à l'ouverture"


def test_open_dispute_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)

    try:
        db.open_dispute(mission_id, 999, "Je ne suis pas le client")
        assert False, "devait lever ValueError"
    except ValueError:
        pass

    assert db.get_mission_by_id(mission_id)["status"] != "disputed"


def test_release_payment_is_blocked_once_mission_is_disputed(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    db.open_dispute(mission_id, 100, "Problème de qualité")

    try:
        db.release_payment(mission_id, 100)
        assert False, "devait lever ValueError"
    except ValueError as error:
        assert "litige" in str(error).lower()

    provider = db.get_provider_by_telegram_id(200)
    assert provider["wallet_balance_usd"] == 0.0, "le client ne doit pas pouvoir contourner le litige et payer quand même"


def test_resolve_dispute_refund_client_credits_client_wallet(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.open_dispute(mission_id, 100, "Mission jamais réalisée")
    client_before = db.get_user_by_telegram_id(100)["wallet_balance_usd"]

    mission = db.resolve_dispute_refund_client(mission_id)

    assert mission["status"] == "cancelled"
    assert mission["payment_status"] == "refunded"
    client_after = db.get_user_by_telegram_id(100)["wallet_balance_usd"]
    assert client_after == client_before + 100.0, "le total payé (100 USD, devis seul) doit revenir au client"
    provider = db.get_provider_by_telegram_id(200)
    assert provider["wallet_balance_usd"] == 0.0, "le prestataire ne doit rien recevoir en cas de remboursement"


def test_resolve_dispute_release_provider_credits_provider_wallet(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.open_dispute(mission_id, 100, "Litige contestable")

    mission = db.resolve_dispute_release_provider(mission_id)

    assert mission["status"] == "completed"
    assert mission["payment_status"] == "released"
    provider = db.get_provider_by_telegram_id(200)
    assert provider["wallet_balance_usd"] == 90.0, "net après commission 10% standard"
    client = db.get_user_by_telegram_id(100)
    assert client["wallet_balance_usd"] == 0.0, "le client ne doit rien récupérer si le prestataire est payé"


def test_resolve_dispute_split_divides_escrow_between_provider_and_client(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.open_dispute(mission_id, 100, "Travail partiellement fait")

    mission = db.resolve_dispute_split(mission_id, 60)

    assert mission["status"] == "completed"
    assert mission["payment_status"] == "released"
    assert mission["net_provider"] == 60.0
    provider = db.get_provider_by_telegram_id(200)
    assert provider["wallet_balance_usd"] == 60.0
    client = db.get_user_by_telegram_id(100)
    assert client["wallet_balance_usd"] == 40.0, "le reste (40%) doit revenir au client"


def test_resolve_dispute_split_rejects_invalid_percentage(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    db.open_dispute(mission_id, 100, "Motif")

    for bad in (-1, 101):
        try:
            db.resolve_dispute_split(mission_id, bad)
            assert False, "devait lever ValueError"
        except ValueError:
            pass


def test_resolve_dispute_functions_reject_a_mission_not_in_dispute(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    # Pas de db.open_dispute ici : mission encore "confirmed", pas "disputed".

    for resolver in (db.resolve_dispute_refund_client, db.resolve_dispute_release_provider):
        try:
            resolver(mission_id)
            assert False, f"{resolver.__name__} devait lever ValueError sur une mission non litigieuse"
        except ValueError:
            pass

    try:
        db.resolve_dispute_split(mission_id, 50)
        assert False, "resolve_dispute_split devait lever ValueError sur une mission non litigieuse"
    except ValueError:
        pass


def test_open_dispute_rejects_reopening_an_already_resolved_mission(tmp_path, monkeypatch):
    """Régression security-reviewer : sans garde d'état, une mission déjà
    résolue (payée au prestataire ou remboursée) pouvait être remise en
    litige puis résolue une seconde fois -> double paiement/remboursement."""
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.release_payment(mission_id, 100)
    assert db.get_mission_by_id(mission_id)["status"] == "completed"

    try:
        db.open_dispute(mission_id, 100, "Je veux quand même me plaindre")
        assert False, "devait lever ValueError"
    except ValueError:
        pass

    mission = db.get_mission_by_id(mission_id)
    assert mission["status"] == "completed", "une mission déjà réglée ne doit pas pouvoir repasser en litige"
    provider_wallet_before_replay = db.get_provider_by_telegram_id(200)["wallet_balance_usd"]
    assert provider_wallet_before_replay == 90.0, "pas de second crédit déclenché par la tentative de réouverture"


def test_open_dispute_rejects_a_mission_never_paid(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(100, "+243800000100", "Cliente", language="fr")
    mission_id = db.create_mission(100, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "Pas encore payée", "urgent": False,
    })

    try:
        db.open_dispute(mission_id, 100, "Motif")
        assert False, "devait lever ValueError : rien n'est en escrow à contester"
    except ValueError:
        pass


def test_disputed_mission_no_longer_listed_after_resolution(tmp_path, monkeypatch):
    """Régression security-reviewer : get_disputed_missions listait
    indéfiniment toute mission ayant un jour eu un dispute_reason, même
    résolue — l'admin voyait un litige déjà réglé avec ses boutons actifs."""
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    db.open_dispute(mission_id, 100, "Motif")
    assert any(m["id"] == mission_id for m in db.get_disputed_missions())

    db.resolve_dispute_refund_client(mission_id)

    assert not any(m["id"] == mission_id for m in db.get_disputed_missions())
    assert db.get_admin_stats()["disputes"] == 0


# --- telegram_bot/payment.py : flow client (motif) -------------------------


def test_client_signale_probleme_starts_dispute_fsm(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))

    callback = DummyCallback(telegram_id=100, data=f"client_report_issue_{mission_id}", bot=DummyBot())
    state = DummyState()
    asyncio.run(payment.client_signale_probleme(callback, state))

    assert state.state == payment.DisputeFlow.reason
    assert state._data["dispute_mission_id"] == mission_id
    assert db.get_mission_by_id(mission_id)["status"] != "disputed", "pas encore de litige tant que le motif n'est pas envoyé"


def test_litige_motif_recu_opens_dispute_and_notifies_provider(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(payment, "get_provider_language", lambda tid: _async_return("fr"))

    bot = DummyBot()
    state = DummyState(data={"dispute_mission_id": mission_id})
    message = DummyMessage(telegram_id=100, text="Le prestataire n'a jamais répondu", bot=bot)
    asyncio.run(payment.litige_motif_recu(message, state))

    mission = db.get_mission_by_id(mission_id)
    assert mission["status"] == "disputed"
    assert mission["dispute_reason"] == "Le prestataire n'a jamais répondu"
    assert state.cleared is True
    assert len(bot.messages) == 1, "le prestataire doit être notifié qu'un litige a été ouvert"
    assert bot.messages[0].chat_id == 200
    assert DummyAsyncClient.last_request["json"]["status"] == "disputed"
    assert DummyAsyncClient.last_request["json"]["dispute_reason"] == "Le prestataire n'a jamais répondu"


def test_litige_motif_recu_rejects_empty_reason(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))

    message = DummyMessage(telegram_id=100, text="   ", bot=DummyBot())
    state = DummyState(data={"dispute_mission_id": mission_id})
    asyncio.run(payment.litige_motif_recu(message, state))

    assert db.get_mission_by_id(mission_id)["status"] != "disputed"
    assert state.cleared is False, "le FSM doit rester actif pour laisser une nouvelle chance"
    assert len(message.answers) == 1


# --- telegram_bot/admin.py : résolution admin --------------------------------


def test_admin_dispute_refund_requires_admin(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    db.open_dispute(mission_id, 100, "Motif")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: False)

    callback = DummyCallback(telegram_id=999, data=f"admin_dispute_refund_{mission_id}", bot=DummyBot())
    asyncio.run(admin.admin_litige_rembourser(callback))

    assert callback.answered is not None
    assert db.get_mission_by_id(mission_id)["status"] == "disputed", "aucune résolution ne doit avoir lieu sans droits admin"


def test_admin_dispute_refund_credits_client_and_notifies_both_parties(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.open_dispute(mission_id, 100, "Mission jamais réalisée")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(admin, "get_provider_language", lambda tid: _async_return("fr"))

    bot = DummyBot()
    callback = DummyCallback(telegram_id=1, data=f"admin_dispute_refund_{mission_id}", bot=bot)
    asyncio.run(admin.admin_litige_rembourser(callback))

    mission = db.get_mission_by_id(mission_id)
    assert mission["payment_status"] == "refunded"
    client = db.get_user_by_telegram_id(100)
    assert client["wallet_balance_usd"] == 100.0
    notified = {m.chat_id for m in bot.messages}
    assert notified == {100, 200}, "client et prestataire doivent tous les deux être notifiés"


def test_admin_dispute_release_credits_provider_and_notifies_both_parties(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.open_dispute(mission_id, 100, "Litige contestable")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(admin, "get_provider_language", lambda tid: _async_return("fr"))

    bot = DummyBot()
    callback = DummyCallback(telegram_id=1, data=f"admin_dispute_release_{mission_id}", bot=bot)
    asyncio.run(admin.admin_litige_payer_prestataire(callback))

    mission = db.get_mission_by_id(mission_id)
    assert mission["payment_status"] == "released"
    provider = db.get_provider_by_telegram_id(200)
    assert provider["wallet_balance_usd"] == 90.0
    notified = {m.chat_id for m in bot.messages}
    assert notified == {100, 200}
    assert DummyAsyncClient.last_request["json"]["payment_status"] == "released"


def test_admin_dispute_split_starts_fsm(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    db.open_dispute(mission_id, 100, "Motif")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)

    callback = DummyCallback(telegram_id=1, data=f"admin_dispute_split_{mission_id}", bot=DummyBot())
    state = DummyState()
    asyncio.run(admin.admin_litige_demarrer_partage(callback, state))

    assert state.state == admin.AdminDisputeSplit.percentage
    assert state._data["dispute_split_mission_id"] == mission_id


def test_admin_dispute_split_divides_between_provider_and_client_and_notifies_both(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch, amount=100.0)
    db.open_dispute(mission_id, 100, "Travail partiellement fait")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)
    monkeypatch.setattr(admin, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(admin, "get_provider_language", lambda tid: _async_return("fr"))

    bot = DummyBot()
    state = DummyState(data={"dispute_split_mission_id": mission_id})
    message = DummyMessage(telegram_id=1, text="70", bot=bot)
    asyncio.run(admin.admin_litige_partage_recu(message, state))

    mission = db.get_mission_by_id(mission_id)
    assert mission["payment_status"] == "released"
    assert mission["net_provider"] == 70.0
    provider = db.get_provider_by_telegram_id(200)
    assert provider["wallet_balance_usd"] == 70.0
    client = db.get_user_by_telegram_id(100)
    assert client["wallet_balance_usd"] == 30.0
    notified = {m.chat_id for m in bot.messages}
    assert notified == {100, 200}
    assert state.cleared is True
    assert DummyAsyncClient.last_request["json"]["refund_amount"] == 30.0
    assert DummyAsyncClient.last_request["json"]["net_provider"] == 70.0, (
        "sans ce champ, le backend créditerait le net_provider ORIGINAL (90) au lieu de la part réduite"
    )


def test_admin_dispute_split_rejects_non_numeric_input_without_crashing(tmp_path, monkeypatch):
    mission_id = _setup_paid_mission(tmp_path, monkeypatch)
    db.open_dispute(mission_id, 100, "Motif")
    monkeypatch.setattr(admin, "is_admin", lambda telegram_id: True)

    state = DummyState(data={"dispute_split_mission_id": mission_id})
    message = DummyMessage(telegram_id=1, text="pas un nombre", bot=DummyBot())
    asyncio.run(admin.admin_litige_partage_recu(message, state))

    assert db.get_mission_by_id(mission_id)["status"] == "disputed", "aucune résolution ne doit avoir lieu"
    assert state.cleared is False, "le FSM doit rester actif pour laisser l'admin réessayer"
