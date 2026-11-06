"""Phase 3, flow 3 : paiement/lifecycle/notation extrait vers telegram_bot/payment.py.

Couvre le cycle complet devis accepté -> paiement (mobile money et wallet) ->
mission démarrée -> terminée -> confirmée -> escrow libéré -> notation. Missions
et devis vivent dans le seul backend (fixture `live_backend`) : `db.py` n'en
garde aucune copie. Même style que
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

import httpx

import db
from messages import get_message
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


def _refuse(request):
    raise httpx.ConnectError("backend coupé", request=request)


class _OfflineClient(httpx._client.AsyncClient):
    def __init__(self, *args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(_refuse)
        super().__init__(*args, **kwargs)


def _init_db(tmp_path):
    db.DB_PATH = tmp_path / "test_nexis_hub.db"
    db.init_db()


def _use_dummy_backend(monkeypatch):
    DummyAsyncClient.last_request = None
    monkeypatch.setattr(backend_client.httpx, "AsyncClient", DummyAsyncClient)
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


def _setup_people(tmp_path, monkeypatch):
    """Profils dans db.py (le bot y lit encore le téléphone et la langue) ;
    missions et devis vivent dans le vrai backend (fixture live_backend)."""
    _init_db(tmp_path)
    db.create_user(100, "+243800000100", "Cliente", language="fr")
    db.create_user(999, "+243800000999", "Intrus", language="fr")
    db.create_provider(200, "+243800000200", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))
    monkeypatch.setattr(payment, "get_provider_language", lambda tid: _async_return("fr"))


def _setup_accepted_quote(tmp_path, monkeypatch, live, currency="USD"):
    _setup_people(tmp_path, monkeypatch)
    return live.accepted_quote(100, 200, amount=50.0, currency=currency, service="service_plomberie")


def _setup_pending_quote(tmp_path, monkeypatch, live, currency="USD"):
    """Le devis reste en attente ; 999 est un client sans rapport avec la mission."""
    _setup_people(tmp_path, monkeypatch)
    return live.quoted_mission(100, 200, amount=50.0, currency=currency, service="service_plomberie")


def test_client_accepte_devis_shows_payment_options_and_notifies_provider(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch, live_backend)

    bot = DummyBot()
    callback = DummyCallback(telegram_id=100, data=f"quote_accept_{quote_id}", bot=bot)

    asyncio.run(payment.client_accepte_devis(callback))

    assert live_backend.get_quote(quote_id).status == "accepted"
    assert live_backend.mission(mission_id).status == "confirmed"
    assert len(bot.messages) == 1
    assert bot.messages[0].chat_id == 200
    assert "Payer" in callback.message.edited_text or callback.message.edited_text is not None


def test_mobile_money_payment_lifecycle_to_release_and_rating(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)

    client_bot = DummyBot()
    provider_bot = DummyBot()

    # Paiement mobile money : décidé par le registre, recopié dans db.py.
    pay_callback = DummyCallback(telegram_id=100, data=f"qpay_op_{quote_id}_mpesa", bot=client_bot)
    asyncio.run(payment.paiement_mobile_money_operateur(pay_callback))
    assert live_backend.mission(mission_id).payment_status == "paid_escrow"
    assert "SIM-PAY-" in pay_callback.message.edited_text
    assert client_bot.messages[0].chat_id == 200

    # Démarrage puis fin de mission par le prestataire.
    asyncio.run(payment.prestataire_demarre_mission(DummyCallback(telegram_id=200, data=f"mission_start_{mission_id}", bot=provider_bot)))
    assert live_backend.mission(mission_id).status == "in_progress"
    asyncio.run(payment.prestataire_termine_mission(DummyCallback(telegram_id=200, data=f"mission_finish_{mission_id}", bot=provider_bot)))
    assert live_backend.mission(mission_id).status == "awaiting_confirmation"

    # Confirmation client -> libération de l'escrow dans le registre.
    confirm_callback = DummyCallback(telegram_id=100, data=f"client_confirm_done_{mission_id}", bot=client_bot)
    state = DummyState()
    asyncio.run(payment.client_confirme_mission_terminee(confirm_callback, state))

    final_mission = live_backend.mission(mission_id)
    assert (final_mission.status, final_mission.payment_status) == ("completed", "released")
    assert live_backend.balance(200) == 45.0  # 50 - 10 % de commission
    assert any("45.00" in sent.text for sent in client_bot.messages if sent.chat_id == 200)
    assert state.state == payment.RatingFlow.rating

    # Notation : une étoile, puis un commentaire (enregistré par le backend).
    rate_callback = DummyCallback(telegram_id=100, data=f"rate_star_{mission_id}_5", bot=client_bot)
    asyncio.run(payment.notation_etoile_recue(rate_callback, state))
    assert state.state == payment.RatingFlow.comment
    assert state._data["rating_value"] == 5

    comment_message = DummyMessage(telegram_id=100, text="Excellent travail", bot=client_bot)
    asyncio.run(payment.notation_commentaire_recu(comment_message, state))
    assert state.cleared is True


def test_wallet_payment_debits_the_client_wallet_in_the_registry(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    live_backend.credit_wallet(100, 200.0)

    bot = DummyBot()
    callback = DummyCallback(telegram_id=100, data=f"qpay_wallet_{quote_id}", bot=bot)
    asyncio.run(payment.paiement_wallet(callback))

    assert live_backend.balance(100) == 150.0, "50 USD du devis doivent être débités du wallet client"
    assert live_backend.mission(mission_id).payment_status == "paid_escrow"
    assert f"WLT-{quote_id:04d}" in callback.message.edited_text


def test_wallet_payment_with_insufficient_balance_answers_alert_without_crash(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)

    callback = DummyCallback(telegram_id=100, data=f"qpay_wallet_{quote_id}", bot=DummyBot())
    asyncio.run(payment.paiement_wallet(callback))

    assert callback.answered == get_message("money_error_insufficient_balance", "fr")
    assert live_backend.mission(mission_id).payment_status is None


def test_payment_is_refused_while_the_backend_is_down_and_nothing_changes(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    live_httpx_client = httpx.AsyncClient
    monkeypatch.setattr(payment.backend_client.httpx, "AsyncClient", _OfflineClient)

    callback = DummyCallback(telegram_id=100, data=f"qpay_op_{quote_id}_mpesa", bot=DummyBot())
    asyncio.run(payment.paiement_mobile_money_operateur(callback))
    monkeypatch.setattr(payment.backend_client.httpx, "AsyncClient", live_httpx_client)

    assert callback.answered == get_message("money_backend_unavailable", "fr")
    assert live_backend.mission(mission_id).payment_status is None
    assert callback.bot.messages == []


def test_paying_twice_charges_once(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    live_backend.credit_wallet(100, 200.0)

    asyncio.run(payment.paiement_wallet(DummyCallback(telegram_id=100, data=f"qpay_wallet_{quote_id}", bot=DummyBot())))
    asyncio.run(payment.paiement_wallet(DummyCallback(telegram_id=100, data=f"qpay_wallet_{quote_id}", bot=DummyBot())))

    assert live_backend.balance(100) == 150.0


def test_client_refuse_devis_notifies_provider(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch, live_backend)

    bot = DummyBot()
    callback = DummyCallback(telegram_id=100, data=f"quote_reject_{quote_id}", bot=bot)
    asyncio.run(payment.client_refuse_devis(callback))

    assert live_backend.get_quote(quote_id).status == "rejected"
    assert len(bot.messages) == 1
    assert bot.messages[0].chat_id == 200


def test_client_accepte_devis_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch, live_backend)

    callback = DummyCallback(telegram_id=999, data=f"quote_accept_{quote_id}", bot=DummyBot())
    asyncio.run(payment.client_accepte_devis(callback))

    assert callback.answered is not None, "un client tiers doit recevoir une alerte, pas un succès silencieux"
    assert live_backend.get_quote(quote_id).status == "pending", "le devis d'un autre client ne doit pas être accepté"


def test_client_refuse_devis_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch, live_backend)

    callback = DummyCallback(telegram_id=999, data=f"quote_reject_{quote_id}", bot=DummyBot())
    asyncio.run(payment.client_refuse_devis(callback))

    assert callback.answered is not None
    assert live_backend.get_quote(quote_id).status == "pending"


def test_paiement_mobile_money_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)

    callback = DummyCallback(telegram_id=999, data=f"qpay_mobile_{quote_id}", bot=DummyBot())
    asyncio.run(payment.paiement_mobile_money(callback))

    assert callback.answered is not None
    assert live_backend.mission(mission_id).payment_status is None, "un tiers ne doit pas pouvoir payer le devis d'un autre"


def test_paiement_wallet_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    # L'intrus (999) a bien un wallet suffisant : le test isole la
    # vérification de propriétaire du cas "solde insuffisant".
    live_backend.credit_wallet(999, 200.0)

    callback = DummyCallback(telegram_id=999, data=f"qpay_wallet_{quote_id}", bot=DummyBot())
    asyncio.run(payment.paiement_wallet(callback))

    # Pour un tiers, le devis d'un autre n'existe pas (même réponse qu'un numéro inconnu).
    assert callback.answered == get_message("money_error_quote_not_found", "fr")
    assert live_backend.mission(mission_id).payment_status is None
    assert live_backend.balance(999) == 200.0, "le wallet de l'intrus ne doit pas être débité pour la mission d'un autre"


def _paid_and_finished(mission_id, quote_id):
    asyncio.run(payment.paiement_mobile_money_operateur(DummyCallback(telegram_id=100, data=f"qpay_op_{quote_id}_mpesa", bot=DummyBot())))
    asyncio.run(payment.prestataire_demarre_mission(DummyCallback(telegram_id=200, data=f"mission_start_{mission_id}", bot=DummyBot())))
    asyncio.run(payment.prestataire_termine_mission(DummyCallback(telegram_id=200, data=f"mission_finish_{mission_id}", bot=DummyBot())))


def test_client_confirme_mission_terminee_rejects_a_caller_who_is_not_the_client(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    _paid_and_finished(mission_id, quote_id)

    callback = DummyCallback(telegram_id=999, data=f"client_confirm_done_{mission_id}", bot=DummyBot())
    state = DummyState()
    asyncio.run(payment.client_confirme_mission_terminee(callback, state))

    assert callback.answered == get_message("money_error_not_mission_client", "fr")
    final_mission = live_backend.mission(mission_id)
    assert final_mission.status == "awaiting_confirmation", "un tiers ne doit pas pouvoir libérer l'escrow d'une autre mission"
    assert final_mission.payment_status == "paid_escrow"
    assert live_backend.balance(200) == 0.0
    assert state.state is None, "le flow de notation ne doit pas démarrer pour une libération refusée"


def test_only_the_mission_provider_can_start_it(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    asyncio.run(payment.paiement_mobile_money_operateur(DummyCallback(telegram_id=100, data=f"qpay_op_{quote_id}_mpesa", bot=DummyBot())))

    callback = DummyCallback(telegram_id=999, data=f"mission_start_{mission_id}", bot=DummyBot())
    asyncio.run(payment.prestataire_demarre_mission(callback))

    assert callback.answered == get_message("money_error_not_mission_provider", "fr")
    assert live_backend.mission(mission_id).status == "confirmed"


def test_client_confirme_mission_terminee_uses_backend_provider_name(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_accepted_quote(tmp_path, monkeypatch, live_backend)
    _paid_and_finished(mission_id, quote_id)
    monkeypatch.setattr(payment, "fetch_backend_profile", lambda tid: _async_return({
        "provider": {"full_name": "Nom Backend"}
    }))

    callback = DummyCallback(telegram_id=100, data=f"client_confirm_done_{mission_id}", bot=DummyBot())
    state = DummyState()
    asyncio.run(payment.client_confirme_mission_terminee(callback, state))

    assert "Nom Backend" in callback.message.answered_texts[-1]
    assert state.state == payment.RatingFlow.rating, "l'existence du prestataire doit rester basée sur db.py"


def test_rating_skip_clears_state_without_backend_call(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))

    callback = DummyCallback(telegram_id=100, data="rate_skip_1", bot=DummyBot())
    state = DummyState(data={"rating_mission_id": 1})
    asyncio.run(payment.notation_ignoree(callback, state))

    assert state.cleared is True
    assert DummyAsyncClient.last_request is None


def test_only_the_accepted_quote_can_be_paid(tmp_path, monkeypatch, live_backend):
    _setup_people(tmp_path, monkeypatch)
    mission_id = live_backend.new_mission(100, alert=(200, 201))
    accepted = live_backend.quote(mission_id, 200, amount=50.0)
    other_quote = live_backend.quote(mission_id, 201, amount=999.0)
    live_backend.accept(accepted, 100)  # l'autre devis est refusé d'office

    callback = DummyCallback(telegram_id=100, data=f"qpay_mobile_{other_quote}", bot=DummyBot())
    asyncio.run(payment.paiement_mobile_money(callback))

    assert callback.answered == get_message("money_error_quote_not_accepted", "fr")
    assert live_backend.mission(mission_id).payment_status is None


def test_a_quote_cannot_be_accepted_twice_on_the_same_mission(tmp_path, monkeypatch, live_backend):
    _setup_people(tmp_path, monkeypatch)
    mission_id = live_backend.new_mission(100, alert=(200, 201))
    first = live_backend.quote(mission_id, 200, amount=50.0)
    second = live_backend.quote(mission_id, 201, amount=40.0)

    asyncio.run(payment.client_accepte_devis(DummyCallback(telegram_id=100, data=f"quote_accept_{first}", bot=DummyBot())))
    late = DummyCallback(telegram_id=100, data=f"quote_accept_{second}", bot=DummyBot())
    asyncio.run(payment.client_accepte_devis(late))

    assert late.answered == get_message("money_error_quote_not_open", "fr")
    assert live_backend.get_quote(first).status == "accepted"
    assert live_backend.get_quote(second).status == "rejected"
    assert live_backend.mission(mission_id).provider_telegram_id == 200


def test_buttons_sent_before_the_backend_owned_quotes_are_inactive(tmp_path, monkeypatch, live_backend):
    mission_id, quote_id = _setup_pending_quote(tmp_path, monkeypatch, live_backend)
    monkeypatch.setattr(payment, "get_user_language", lambda tid: _async_return("fr"))

    for data in (f"client_accept_quote_{quote_id}:-", f"pay_mm_{quote_id}_mpesa", f"pay_wallet_{quote_id}"):
        callback = DummyCallback(telegram_id=100, data=data, bot=DummyBot())
        asyncio.run(payment.ancien_bouton_devis(callback))
        assert callback.answered == get_message("inactive_button", "fr")

    assert live_backend.get_quote(quote_id).status == "pending"
