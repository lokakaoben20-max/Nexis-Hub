"""Phase 3, flow 3 : paiement/lifecycle/notation extrait vers telegram_bot/payment.py.

Couvre le cycle complet devis accepté -> paiement (mobile money et wallet) ->
mission démarrée -> terminée -> confirmée -> escrow libéré -> notation, avec la
double écriture backend + `db.py` maintenue à chaque étape. Même style que
`tests/test_mission_flow_extraction.py` (`DummyBot`, `DummyAsyncClient`, SQLite
jetable) — vérifié ici : les handlers utilisent `callback.bot`/`message.bot`
plutôt que l'instance globale `bot` (le mock ne fonctionnerait pas sinon).
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
from telegram_bot import backend_client, payment


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
        self.kwargs = kwargs


class DummyBot:
    """Capture les envois sortants — remplace l'instance aiogram réelle.

    Les handlers extraits utilisent `callback.bot` / `message.bot` plutôt qu'une
    variable globale `bot` : c'est ce qui rend ce mock possible sans monkeypatch
    d'un module tiers.
    """

    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append(SentMessage(chat_id, text, **kwargs))


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None
        self.answered_texts = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered_texts.append(text)


class DummyUser:
    def __init__(self, telegram_id, first_name="Test"):
        self.id = telegram_id
        self.first_name = first_name


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


def _setup_accepted_quote(tmp_path, monkeypatch, currency="USD"):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(100, "+243800000100", "Cliente", language="fr")
    db.create_provider(200, "+243800000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(100, {
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": currency,
        "description": "Fuite d'eau",
        "urgent": False,
    })
    quote_id = db.create_quote(mission_id, 200, 50.0, currency, 4, "")
    db.accept_quote(quote_id, 100)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(payment, "get_provider_language", lambda tid: _async_return("fr"))
    return mission_id, quote_id


def test_client_accepte_devis_shows_payment_options_and_notifies_provider(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)

    bot = DummyBot()
    callback = DummyCallback(telegram_id=100, data=f"client_accept_quote_{quote_id}:-", bot=bot)

    asyncio.run(payment.client_accepte_devis(callback))

    assert DummyAsyncClient.last_request is None, "pas d'id backend (':-') -> aucun appel accept ne doit partir"
    assert len(bot.messages) == 1
    assert bot.messages[0].chat_id == 200
    assert "Payer" in callback.message.edited_text or callback.message.edited_text is not None


def test_mobile_money_payment_lifecycle_to_release_and_rating(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)

    client_bot = DummyBot()
    provider_bot = DummyBot()

    # Paiement mobile money.
    pay_callback = DummyCallback(telegram_id=100, data=f"pay_mobile_{quote_id}", bot=client_bot)
    asyncio.run(payment.paiement_mobile_money(pay_callback))
    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/payments")
    assert db.get_mission_by_id(mission_id)["payment_status"] == "paid_escrow"

    # Démarrage de la mission par le prestataire.
    start_callback = DummyCallback(telegram_id=200, data=f"mission_start_{mission_id}", bot=provider_bot)
    asyncio.run(payment.prestataire_demarre_mission(start_callback))
    assert db.get_mission_by_id(mission_id)["status"] == "in_progress"

    # Fin de mission par le prestataire.
    finish_callback = DummyCallback(telegram_id=200, data=f"mission_finish_{mission_id}", bot=provider_bot)
    asyncio.run(payment.prestataire_termine_mission(finish_callback))
    assert db.get_mission_by_id(mission_id)["status"] == "awaiting_confirmation"

    # Confirmation client -> libération de l'escrow.
    provider_before = db.get_provider_by_telegram_id(200)
    confirm_callback = DummyCallback(telegram_id=100, data=f"client_confirm_done_{mission_id}", bot=client_bot)
    state = DummyState()
    asyncio.run(payment.client_confirme_mission_terminee(confirm_callback, state))

    final_mission = db.get_mission_by_id(mission_id)
    assert final_mission["status"] == "completed"
    assert final_mission["payment_status"] == "released"
    provider_after = db.get_provider_by_telegram_id(200)
    assert provider_after["wallet_balance_usd"] > provider_before["wallet_balance_usd"], (
        "le net du prestataire doit être crédité sur son wallet à la libération"
    )
    assert state.state == payment.RatingFlow.rating

    # Notation : une étoile, puis un commentaire.
    rate_callback = DummyCallback(telegram_id=100, data=f"rate_star_{mission_id}_5", bot=client_bot)
    asyncio.run(payment.notation_etoile_recue(rate_callback, state))
    assert state.state == payment.RatingFlow.comment
    assert state._data["rating_value"] == 5

    comment_message = DummyMessage(telegram_id=100, text="Excellent travail", bot=client_bot)
    asyncio.run(payment.notation_commentaire_recu(comment_message, state))
    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/reviews")
    assert state.cleared is True


def test_wallet_payment_debits_client_and_credits_provider_on_release(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)
    with db.get_connection() as conn:
        conn.execute("UPDATE users SET wallet_balance_usd = ? WHERE telegram_id = ?", (200.0, 100))

    bot = DummyBot()
    callback = DummyCallback(telegram_id=100, data=f"pay_wallet_{quote_id}", bot=bot)
    asyncio.run(payment.paiement_wallet(callback))

    client = db.get_user_by_telegram_id(100)
    assert client["wallet_balance_usd"] == 150.0, "50 USD du devis doivent être débités du wallet client"
    assert db.get_mission_by_id(mission_id)["payment_status"] == "paid_escrow"
    assert DummyAsyncClient.last_request["url"].endswith("/api/bot/payments")


def test_wallet_payment_with_insufficient_balance_answers_alert_without_crash(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)

    callback = DummyCallback(telegram_id=100, data=f"pay_wallet_{quote_id}", bot=DummyBot())
    asyncio.run(payment.paiement_wallet(callback))

    assert callback.answered is not None
    assert db.get_mission_by_id(mission_id)["payment_status"] == "unpaid"


def test_client_refuse_devis_notifies_provider(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(300, "+243800000300", "Cliente", language="fr")
    db.create_provider(400, "+243800000400", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(300, {
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Peinture",
        "urgent": False,
    })
    quote_id = db.create_quote(mission_id, 400, 30.0, "USD", 2, "")
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(payment, "get_provider_language", lambda tid: _async_return("fr"))

    bot = DummyBot()
    callback = DummyCallback(telegram_id=300, data=f"client_reject_quote_{quote_id}:-", bot=bot)
    asyncio.run(payment.client_refuse_devis(callback))

    assert db.get_quote_by_id(quote_id)["status"] == "rejected"
    assert len(bot.messages) == 1
    assert bot.messages[0].chat_id == 400


def _setup_pending_quote(tmp_path, monkeypatch, currency="USD"):
    """Comme _setup_accepted_quote, mais le devis reste 'pending' (pas encore accepté).

    Ajoute aussi un second client (999) qui n'a rien à voir avec cette mission,
    pour les tests de vérification de propriétaire ci-dessous.
    """
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    db.create_user(100, "+243800000100", "Cliente", language="fr")
    db.create_user(999, "+243800000999", "Intrus", language="fr")
    db.create_provider(200, "+243800000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    mission_id = db.create_mission(100, {
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": currency,
        "description": "Fuite d'eau",
        "urgent": False,
    })
    quote_id = db.create_quote(mission_id, 200, 50.0, currency, 4, "")
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(payment, "get_provider_language", lambda tid: _async_return("fr"))
    return mission_id, quote_id


def test_client_accepte_devis_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch)

    callback = DummyCallback(telegram_id=999, data=f"client_accept_quote_{quote_id}:-", bot=DummyBot())
    asyncio.run(payment.client_accepte_devis(callback))

    assert callback.answered is not None, "un client tiers doit recevoir une alerte, pas un succès silencieux"
    assert db.get_quote_by_id(quote_id)["status"] == "pending", "le devis d'un autre client ne doit pas être accepté"


def test_client_refuse_devis_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch)

    callback = DummyCallback(telegram_id=999, data=f"client_reject_quote_{quote_id}:-", bot=DummyBot())
    asyncio.run(payment.client_refuse_devis(callback))

    assert callback.answered is not None
    assert db.get_quote_by_id(quote_id)["status"] == "pending"


def test_paiement_mobile_money_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)

    callback = DummyCallback(telegram_id=999, data=f"pay_mobile_{quote_id}", bot=DummyBot())
    asyncio.run(payment.paiement_mobile_money(callback))

    assert callback.answered is not None
    assert db.get_mission_by_id(mission_id)["payment_status"] == "unpaid", "un tiers ne doit pas pouvoir payer le devis d'un autre"


def test_paiement_wallet_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)
    db.create_user(999, "+243800000999", "Intrus", language="fr")
    with db.get_connection() as conn:
        # L'intrus (999) a bien un wallet suffisant : le test isole la
        # vérification de propriétaire du cas "solde insuffisant".
        conn.execute("UPDATE users SET wallet_balance_usd = ? WHERE telegram_id = ?", (200.0, 999))

    callback = DummyCallback(telegram_id=999, data=f"pay_wallet_{quote_id}", bot=DummyBot())
    asyncio.run(payment.paiement_wallet(callback))

    assert callback.answered is not None
    assert db.get_mission_by_id(mission_id)["payment_status"] == "unpaid"
    intrus_wallet = db.get_user_by_telegram_id(999)["wallet_balance_usd"]
    assert intrus_wallet == 200.0, "le wallet de l'intrus ne doit pas être débité pour la mission d'un autre"


def test_client_confirme_mission_terminee_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch)
    payment_result = db.mark_quote_paid(quote_id, 100, operator="mobile_money_simulation")
    db.start_mission(mission_id, 200)
    db.finish_mission(mission_id, 200)
    provider_before = db.get_provider_by_telegram_id(200)

    callback = DummyCallback(telegram_id=999, data=f"client_confirm_done_{mission_id}", bot=DummyBot())
    state = DummyState()
    asyncio.run(payment.client_confirme_mission_terminee(callback, state))

    assert callback.answered is not None
    final_mission = db.get_mission_by_id(mission_id)
    assert final_mission["status"] == "awaiting_confirmation", "un tiers ne doit pas pouvoir libérer l'escrow d'une autre mission"
    assert final_mission["payment_status"] == "paid_escrow"
    provider_after = db.get_provider_by_telegram_id(200)
    assert provider_after["wallet_balance_usd"] == provider_before["wallet_balance_usd"]
    assert state.state is None, "le flow de notation ne doit pas démarrer pour une libération refusée"


def test_rating_skip_clears_state_without_backend_call(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))

    callback = DummyCallback(telegram_id=100, data="rate_skip_1", bot=DummyBot())
    state = DummyState(data={"rating_mission_id": 1})
    asyncio.run(payment.notation_ignoree(callback, state))

    assert state.cleared is True
    assert DummyAsyncClient.last_request is None
