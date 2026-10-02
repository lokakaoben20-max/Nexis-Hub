"""Phase 3, dernier groupe : missions/wallet extrait vers telegram_bot/dashboard.py.

Ce groupe (affichage services prestataire, missions/wallet client et
prestataire, historique, aide) n'avait aucun test dédié avant cette
extraction — couvert ici pour la première fois, même style que
`tests/test_payment_flow_extraction.py` (`DummyCallback`/`DummyMessage`,
SQLite jetable). `fetch_backend_missions` (déplacé) et
`format_mission_client`/`build_history_rich_message` (déplacés) sont déjà
couverts par `tests/test_v5_missions_flow.py` et
`tests/test_bot_backend_sync.py` respectivement — pas dupliqué ici.
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
from messages import get_message
from telegram_bot import backend_client, dashboard


class DummyMessageObject:
    def __init__(self):
        self.edited_text = None
        self.answered_texts = []

    async def edit_text(self, text=None, parse_mode=None, reply_markup=None, rich_message=None):
        if rich_message is not None:
            raise TypeError("rich_message non supporté par ce mock, comme Telegram sur certains clients")
        self.edited_text = text

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answered_texts.append(text)


class DummyUser:
    def __init__(self, telegram_id):
        self.id = telegram_id
        self.first_name = "Test"


class DummyCallback:
    def __init__(self, telegram_id, data=""):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessageObject()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


class DummyMessage:
    def __init__(self, telegram_id, text=""):
        self.from_user = DummyUser(telegram_id)
        self.text = text
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
    # dashboard.py fait `from telegram_bot.backend_client import fetch_backend_profile`
    # au niveau module : ce nom est lié dans le namespace de dashboard à
    # l'import, donc patcher uniquement backend_client.fetch_backend_profile
    # ne touche pas dashboard.fetch_backend_missions (trouvaille security-reviewer).
    monkeypatch.setattr(backend_client, "fetch_backend_profile", lambda telegram_id: _async_return(None))
    monkeypatch.setattr(dashboard, "fetch_backend_profile", lambda telegram_id: _async_return(None))


async def _async_return(value):
    return value


# --- services prestataire ------------------------------------------------


def test_afficher_services_prestataire_requires_profile(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)

    callback = DummyCallback(telegram_id=999)
    asyncio.run(dashboard.afficher_services_prestataire(callback))

    assert callback.answered is not None


def test_afficher_services_prestataire_lists_active_and_pending(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3001
    db.create_provider(telegram_id, "+243800003001", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    db.create_service_request(telegram_id, "Service manquant", "Description suffisamment longue.")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_services_prestataire(callback))

    assert "Plomberie" in callback.message.edited_text or "plomberie" in callback.message.edited_text.lower()
    assert "SRV-" in callback.message.edited_text


def test_afficher_services_prestataire_uses_backend_services_when_available(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3002
    db.create_provider(telegram_id, "+243800003002", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    monkeypatch.setattr(dashboard, "fetch_backend_profile", lambda tid: _async_return({
        "provider": {"services": ["service_electricite"]}
    }))

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_services_prestataire(callback))

    text = callback.message.edited_text.lower()
    assert "electricit" in text
    assert "plomberie" not in text, "la liste locale ne doit plus apparaître quand le backend répond"


def test_proposer_service_manquant_starts_fsm(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3002
    db.create_provider(telegram_id, "+243800003002", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    callback = DummyCallback(telegram_id)
    state = DummyState()
    asyncio.run(dashboard.proposer_service_manquant(callback, state))

    assert state.state == dashboard.ProviderServiceRequest.service_name


def test_recevoir_nom_service_manquant_rejects_too_short(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3003
    db.create_provider(telegram_id, "+243800003003", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    message = DummyMessage(telegram_id, text="ab")
    state = DummyState()
    asyncio.run(dashboard.recevoir_nom_service_manquant(message, state))

    assert "missing_service_name" not in state._data
    assert len(message.answers) == 1


def test_full_service_request_flow_creates_pending_request(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3004
    db.create_provider(telegram_id, "+243800003004", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    state = DummyState()
    asyncio.run(dashboard.recevoir_nom_service_manquant(DummyMessage(telegram_id, text="Service exotique"), state))
    assert state.state == dashboard.ProviderServiceRequest.description

    asyncio.run(dashboard.recevoir_description_service_manquant(
        DummyMessage(telegram_id, text="Description suffisamment longue pour passer la validation."), state
    ))

    assert state.cleared is True
    requests = db.get_provider_service_requests(telegram_id)
    assert len(requests) == 1
    assert requests[0]["service_name"] == "Service exotique"
    assert requests[0]["status"] == "pending"


def _submit_service_request(telegram_id):
    state = DummyState({"missing_service_name": "Service exotique"})
    asyncio.run(dashboard.recevoir_description_service_manquant(
        DummyMessage(telegram_id, text="Description suffisamment longue pour passer la validation."), state
    ))
    return db.get_provider_service_requests(telegram_id)


def test_service_request_is_mirrored_to_backend_and_keeps_backend_id(tmp_path, monkeypatch):
    """Étape C : la proposition est recopiée au backend et son id backend est
    gardé en local, pour que la décision admin puisse suivre."""
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3010
    db.create_provider(telegram_id, "+243800003010", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    sent = []

    async def fake_sync(provider_telegram_id, service_name, description=""):
        sent.append((provider_telegram_id, service_name, description))
        return {"status": "ok", "service_request": {"id": 77}}

    monkeypatch.setattr(dashboard, "sync_service_request_to_backend", fake_sync)

    requests = _submit_service_request(telegram_id)

    assert sent == [(telegram_id, "Service exotique", "Description suffisamment longue pour passer la validation.")]
    assert len(requests) == 1
    assert requests[0]["backend_request_id"] == 77


def test_service_request_still_created_locally_when_backend_unavailable(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3011
    db.create_provider(telegram_id, "+243800003011", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    async def failing_sync(*args, **kwargs):
        raise RuntimeError("backend indisponible")

    monkeypatch.setattr(dashboard, "sync_service_request_to_backend", failing_sync)

    requests = _submit_service_request(telegram_id)

    assert len(requests) == 1
    assert requests[0]["status"] == "pending"
    assert requests[0]["backend_request_id"] is None


# --- missions / wallet client ---------------------------------------------


def test_afficher_missions_client_shows_empty_state(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3005
    db.create_user(telegram_id, "+243800003005", "Cliente", language="fr")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_client(callback))

    assert callback.message.edited_text is not None


def test_afficher_missions_client_lists_local_mission_when_backend_unavailable(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3006
    db.create_user(telegram_id, "+243800003006", "Cliente", language="fr")
    db.create_mission(telegram_id, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "Fuite d'eau", "urgent": False,
    })

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_client(callback))

    assert callback.message.edited_text is not None
    assert "NXH-0001" in callback.message.edited_text
    assert "sqlite3.Row" not in callback.message.edited_text


def test_afficher_wallet_client_requires_existing_client(tmp_path, monkeypatch):
    _init_db(tmp_path)

    callback = DummyCallback(telegram_id=999)
    asyncio.run(dashboard.afficher_wallet_client(callback))

    assert callback.answered == "Client introuvable."


def test_afficher_wallet_client_shows_balances(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3007
    db.create_user(telegram_id, "+243800003007", "Cliente", language="fr")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_client(callback))

    assert callback.message.edited_text is not None


# --- missions / wallet prestataire -----------------------------------------


def test_afficher_missions_prestataire_shows_empty_state(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3008
    db.create_provider(telegram_id, "+243800003008", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_prestataire(callback))

    assert callback.message.edited_text is not None


def test_afficher_missions_prestataire_prefers_backend_payload(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3009
    db.create_provider(telegram_id, "+243800003009", "Prestataire", ["service_peinture"], ["Gombe"], language="fr")
    monkeypatch.setattr(
        dashboard,
        "fetch_backend_profile",
        lambda _telegram_id: _async_return(
            {
                "provider_missions": [
                    {
                        "mission_id": 42,
                        "service": "service_peinture",
                        "commune": "Gombe",
                        "status": "in_progress",
                        "payment_status": "paid_escrow",
                        "client_name": "Client V5",
                    }
                ]
            }
        ),
    )

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_prestataire(callback))

    assert "NXH-0042" in callback.message.edited_text
    assert "Client V5" in callback.message.edited_text
    assert "En cours" in callback.message.edited_text


def test_afficher_wallet_prestataire_requires_profile(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)

    callback = DummyCallback(telegram_id=999)
    asyncio.run(dashboard.afficher_wallet_prestataire(callback))

    assert callback.answered is not None


def test_afficher_wallet_client_reads_the_registry(tmp_path, monkeypatch, live_backend):
    """Le registre du backend est la seule source des soldes."""
    _init_db(tmp_path)
    telegram_id = 3012
    db.create_user(telegram_id, "+243800003012", "Cliente", language="fr")
    live_backend.credit_wallet(telegram_id, 42.5)
    live_backend.credit_wallet(telegram_id, 7000.0, currency="CDF")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_client(callback))

    assert "42.50 USD" in callback.message.edited_text
    assert "7000.00 CDF" in callback.message.edited_text


def test_afficher_wallet_client_shows_unavailable_when_the_backend_is_down(tmp_path, monkeypatch):
    _init_db(tmp_path)
    telegram_id = 3013
    db.create_user(telegram_id, "+243800003013", "Cliente", language="fr")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_client(callback))

    assert callback.message.edited_text == get_message("wallet_unavailable", "fr")


def test_client_and_provider_screens_show_the_same_single_wallet(tmp_path, monkeypatch, live_backend):
    _init_db(tmp_path)
    telegram_id = 3014
    db.create_user(telegram_id, "+243800003014", "Prestataire", language="fr")
    db.create_provider(telegram_id, "+243800003014", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")
    live_backend.credit_wallet(telegram_id, 88.0)

    provider_callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_prestataire(provider_callback))
    client_callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_client(client_callback))

    assert "88.00 USD" in provider_callback.message.edited_text
    assert "88.00 USD" in client_callback.message.edited_text


def test_afficher_wallet_prestataire_shows_unavailable_when_the_backend_is_down(tmp_path, monkeypatch):
    _init_db(tmp_path)
    telegram_id = 3015
    db.create_provider(telegram_id, "+243800003015", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_prestataire(callback))

    assert callback.message.edited_text == get_message("wallet_unavailable", "fr")


# --- historique / aide ------------------------------------------------------


def test_afficher_historique_client_filters_terminal_statuses_only(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    client_id, provider_id = 3009, 3109
    db.create_user(client_id, "+243800003009", "Cliente", language="fr")
    db.create_provider(provider_id, "+243800003109", "Prestataire", ["service_plomberie"], ["Gombe"], language="fr")

    # Mission active (pas encore terminale) : ne doit pas apparaître.
    db.create_mission(client_id, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "En cours", "urgent": False,
    })

    # Mission terminale (payée puis libérée -> status completed).
    mission_id = db.create_mission(client_id, {
        "service": "service_electricite", "commune": "Gombe", "currency": "USD",
        "description": "Terminée", "urgent": False,
    })
    quote_id = db.create_quote(mission_id, provider_id, 50.0, "USD", 2, "")
    db.accept_quote(quote_id, client_id)
    # État recopié du backend après une libération (seul le backend règle).
    db.apply_backend_mission(mission_id, {
        "status": "completed", "payment_status": "released", "provider_telegram_id": provider_id,
        "commission_amount": 5.0, "total_client": 50.0, "net_provider": 45.0,
    })

    callback = DummyCallback(client_id)
    asyncio.run(dashboard.afficher_historique_client(callback))

    assert callback.message.edited_text is not None
    assert f"NXH-{mission_id:04d}" in callback.message.edited_text
    assert callback.message.edited_text.count("NXH-") == 1, "seule la mission terminale doit apparaître dans l'historique"


def test_afficher_historique_client_shows_empty_state_when_nothing_terminal(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3010
    db.create_user(telegram_id, "+243800003010", "Cliente", language="fr")
    db.create_mission(telegram_id, {
        "service": "service_plomberie", "commune": "Gombe", "currency": "USD",
        "description": "En cours", "urgent": False,
    })

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_historique_client(callback))

    assert callback.message.edited_text is not None


def test_afficher_aide_client_falls_back_to_plain_text(tmp_path, monkeypatch):
    _init_db(tmp_path)
    _use_dummy_backend(monkeypatch)
    telegram_id = 3011
    db.create_user(telegram_id, "+243800003011", "Cliente", language="fr")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_aide_client(callback))

    assert callback.message.edited_text is not None
