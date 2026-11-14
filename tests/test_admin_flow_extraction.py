"""Phase 3, groupe admin : extraction vers telegram_bot/admin.py (voir AGENTS.md).

Complète `tests/test_dispute_flow.py` (résolution des litiges) et
`tests/test_provider_verification.py` (vérification/refus) : couvre ici les
handlers pas encore testés ailleurs (suspension/réactivation prestataire,
services proposés, accès admin) et vérifie que les 6 handlers qui utilisaient
encore le `bot` global dans `main.py` (`admin_accept_service`,
`admin_verify_provider`, `admin_reject_provider`, `admin_suspend_provider`,
`admin_unsuspend_provider`, `admin_reject_service`) utilisent bien
`callback.bot` après extraction — même style que
`tests/test_payment_flow_extraction.py` (`DummyBot` capture les envois via
`callback.bot`, pas une instance globale, donc le mock ne fonctionnerait pas
sinon).
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from telegram_bot import admin, backend_client


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
        DummyAsyncClient.last_request = {"method": "post", "url": url, "json": json}
        return DummyResponse({"status": "ok"})

    async def patch(self, url, json=None):
        DummyAsyncClient.last_request = {"method": "patch", "url": url, "json": json}
        return DummyResponse({"status": "ok"})

    async def get(self, url, params=None):
        return DummyResponse({"client": None, "provider": None})


class DummyBot:
    """Capture les envois sortants via `callback.bot` (voir docstring du module)."""

    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text, **kwargs):
        self.messages.append((chat_id, text))


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None
        self.answered_texts = []

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered_texts.append(text)


class DummyUser:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Admin"


class DummyCallback:
    def __init__(self, telegram_id, data="", bot=None):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessageObject()
        self.bot = bot or DummyBot()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


ADMIN = 999


def _propose(live, telegram_id, name="Service exotique"):
    """Proposition de service faite par le prestataire, enregistrée par le backend."""
    live.provider(telegram_id, "Proposeur")
    return asyncio.run(backend_client.propose_service(telegram_id, name, "Description suffisamment longue."))["id"]


def _requests(live):
    from backend.app.models import ProviderServiceRequest

    with live.database.SessionLocal() as session:
        return {request.id: request.status for request in session.query(ProviderServiceRequest).all()}


# --- accès admin -------------------------------------------------------------


def test_non_admin_is_refused_on_any_handler(live_backend):
    callback = DummyCallback(telegram_id=ADMIN, data="admin_stats")
    asyncio.run(admin.admin_stats(callback))

    assert callback.answered == "Accès admin refusé."
    assert callback.message.edited_text is None, "aucune donnée admin ne doit être révélée à un non-admin"


def test_admin_stats_come_from_the_backend(live_backend):
    live_backend.grant_admin(ADMIN)
    live_backend.client(2100)
    live_backend.provider(2101)
    live_backend.provider(2102, verified=False)
    _propose(live_backend, 2103)

    callback = DummyCallback(telegram_id=ADMIN, data="admin_stats")
    asyncio.run(admin.admin_stats(callback))

    text = callback.message.edited_text
    assert "Clients : <b>1</b>" in text
    assert "Prestataires : <b>3</b> (à vérifier : <b>1</b>)" in text
    assert "Services proposés en attente : <b>1</b>" in text


# --- vérification / suspension / réactivation prestataire --------------------


def test_admin_provider_actions_by_account(live_backend):
    live_backend.grant_admin(ADMIN)
    # Un autre prestataire d'abord : le compte et le telegram_id diffèrent.
    live_backend.provider(2020, "Autre", verified=False)
    account_id = live_backend.provider(2021, "Cible", verified=False)

    bot = DummyBot()
    asyncio.run(admin.admin_verify_provider(DummyCallback(ADMIN, data=f"admin_verify_provider_acc_{account_id}", bot=bot)))
    assert live_backend.profile(2021)["provider"]["status"] == "available"
    assert live_backend.profile(2020)["provider"]["status"] == "pending_verification", "aucun autre prestataire touché"

    asyncio.run(admin.admin_suspend_provider(DummyCallback(ADMIN, data=f"admin_suspend_provider_acc_{account_id}", bot=bot)))
    assert live_backend.profile(2021)["provider"]["is_suspended"] is True
    asyncio.run(admin.admin_unsuspend_provider(DummyCallback(ADMIN, data=f"admin_unsuspend_provider_acc_{account_id}", bot=bot)))
    assert live_backend.profile(2021)["provider"]["is_suspended"] is False
    assert [chat_id for chat_id, _ in bot.messages] == [2021, 2021, 2021], "prévenu par callback.bot à chaque décision"


def test_a_verified_provider_cannot_be_rejected(live_backend):
    live_backend.grant_admin(ADMIN)
    account_id = live_backend.provider(2022)

    callback = DummyCallback(ADMIN, data=f"admin_reject_provider_acc_{account_id}")
    asyncio.run(admin.admin_reject_provider(callback))

    assert callback.answered == admin.PROVIDER_REFUSALS["provider_not_pending"]
    assert live_backend.profile(2022)["provider"]["status"] == "available"


def test_admin_provider_button_with_unknown_or_old_id(live_backend):
    live_backend.grant_admin(ADMIN)

    unknown = DummyCallback(ADMIN, data="admin_suspend_provider_acc_77777")
    asyncio.run(admin.admin_suspend_provider(unknown))
    assert unknown.answered == "Prestataire introuvable."

    for data in ("admin_reject_provider_tg_77777", "admin_reject_provider_12", "admin_reject_provider_acc_abc"):
        callback = DummyCallback(ADMIN, data=data)
        asyncio.run(admin.admin_reject_provider(callback))
        assert callback.answered.startswith("Bouton périmé")


def test_admin_provider_decision_says_so_when_the_backend_is_down(monkeypatch):
    monkeypatch.setattr(admin, "admin_status", lambda telegram_id: asyncio.sleep(0, result=True))

    callback = DummyCallback(ADMIN, data="admin_verify_provider_acc_1")
    asyncio.run(admin.admin_verify_provider(callback))

    assert "indisponible" in callback.answered
    assert callback.message.edited_text is None


def _button_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def test_provider_admin_buttons_carry_the_nexis_account():
    from telegram_bot import keyboards

    assert _button_data(keyboards.clavier_admin_provider(424242)) == [
        "admin_verify_provider_acc_424242",
        "admin_reject_provider_acc_424242",
        "admin_suspend_provider_acc_424242",
        "admin_unsuspend_provider_acc_424242",
        "admin_home",
    ]
    assert _button_data(keyboards.clavier_admin_new_provider(424242)) == [
        "admin_verify_provider_acc_424242",
        "admin_reject_provider_acc_424242",
    ]
    assert all(len(data.encode()) <= 64 for data in _button_data(keyboards.clavier_admin_provider(10**15)))


# --- services proposés --------------------------------------------------------


def test_admin_accept_service_notifies_provider_via_callback_bot(live_backend):
    live_backend.grant_admin(ADMIN)
    request_id = _propose(live_backend, 2003)

    bot = DummyBot()
    asyncio.run(admin.admin_accept_service(DummyCallback(ADMIN, data=f"admin_accept_service_{request_id}", bot=bot)))

    assert _requests(live_backend)[request_id] == "accepted"
    assert [chat_id for chat_id, _ in bot.messages] == [2003], "la notification part vers le prestataire, pas l'admin"


def test_admin_reject_service_notifies_provider_via_callback_bot(live_backend):
    live_backend.grant_admin(ADMIN)
    request_id = _propose(live_backend, 2004, "Service refusé")

    bot = DummyBot()
    asyncio.run(admin.admin_reject_service(DummyCallback(ADMIN, data=f"admin_reject_service_{request_id}", bot=bot)))

    assert _requests(live_backend)[request_id] == "rejected"
    assert [chat_id for chat_id, _ in bot.messages] == [2004]


def test_admin_service_requests_lists_pending_only(live_backend):
    live_backend.grant_admin(ADMIN)
    accepted_id = _propose(live_backend, 2005, "Déjà traité")
    asyncio.run(admin.admin_accept_service(DummyCallback(ADMIN, data=f"admin_accept_service_{accepted_id}")))
    pending_id = _propose(live_backend, 2005, "En attente")

    callback = DummyCallback(ADMIN, data="admin_service_requests")
    asyncio.run(admin.admin_service_requests(callback))

    listed_ids = {int(text.split("SRV-")[1][:4]) for text in callback.message.answered_texts if "SRV-" in text}
    assert listed_ids == {pending_id}, "une proposition déjà traitée n'apparaît plus dans la file"


def test_admin_cannot_decide_a_service_request_twice(live_backend):
    """Un second clic (refuser après accepter) ne change rien et ne
    renotifie pas le prestataire."""
    live_backend.grant_admin(ADMIN)
    request_id = _propose(live_backend, 2010)

    bot = DummyBot()
    asyncio.run(admin.admin_accept_service(DummyCallback(ADMIN, data=f"admin_accept_service_{request_id}", bot=bot)))
    second = DummyCallback(ADMIN, data=f"admin_reject_service_{request_id}", bot=bot)
    asyncio.run(admin.admin_reject_service(second))

    assert _requests(live_backend)[request_id] == "accepted"
    assert second.answered == "Cette proposition a déjà été traitée."
    assert second.message.edited_text is None
    assert len(bot.messages) == 1, "le prestataire n'est notifié qu'une fois"
