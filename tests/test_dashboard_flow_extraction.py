"""Phase 3, dernier groupe : missions/wallet extrait vers telegram_bot/dashboard.py.

Ce groupe (affichage services prestataire, missions/wallet client et
prestataire, historique, aide) n'avait aucun test dédié avant cette
extraction — couvert ici pour la première fois, même style que
`tests/test_payment_flow_extraction.py` (`DummyCallback`/`DummyMessage`).
Profils, propositions de services, missions et soldes sont lus dans le vrai
backend (fixture `live_backend`).
"""

import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from messages import get_message
from telegram_bot import dashboard


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


def _requests(live, telegram_id):
    from backend.app.models import ProviderServiceRequest

    with live.database.SessionLocal() as session:
        return [
            (request.service_name, request.status)
            for request in session.query(ProviderServiceRequest).order_by(ProviderServiceRequest.id)
        ]


# --- services prestataire ------------------------------------------------


def test_afficher_services_prestataire_requires_profile(live_backend):
    live_backend.client(999)

    callback = DummyCallback(telegram_id=999)
    asyncio.run(dashboard.afficher_services_prestataire(callback))

    assert callback.answered == get_message("provider_profile_required", "fr")
    assert callback.message.edited_text is None


def test_afficher_services_prestataire_lists_the_backend_services_and_proposals(live_backend):
    from telegram_bot import backend_client

    telegram_id = 3001
    live_backend.provider(telegram_id, services=["service_electricite"])
    asyncio.run(backend_client.propose_service(telegram_id, "Service manquant", "Description suffisamment longue."))

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_services_prestataire(callback))

    text = callback.message.edited_text
    assert "lectricit" in text
    assert "Plomberie" not in text
    assert "SRV-" in text and "Service manquant" in text


def test_afficher_services_prestataire_says_so_when_the_backend_is_down():
    callback = DummyCallback(telegram_id=3001)
    asyncio.run(dashboard.afficher_services_prestataire(callback))

    assert callback.answered == get_message("service_unavailable", "fr")
    assert callback.message.edited_text is None


def test_proposer_service_manquant_starts_fsm(live_backend):
    telegram_id = 3002
    live_backend.provider(telegram_id)

    callback = DummyCallback(telegram_id)
    state = DummyState()
    asyncio.run(dashboard.proposer_service_manquant(callback, state))

    assert state.state == dashboard.ProviderServiceRequest.service_name


def test_recevoir_nom_service_manquant_rejects_too_short():
    message = DummyMessage(3003, text="ab")
    state = DummyState()
    asyncio.run(dashboard.recevoir_nom_service_manquant(message, state))

    assert "missing_service_name" not in state._data
    assert len(message.answers) == 1


def test_full_service_request_flow_creates_pending_request_in_the_backend(live_backend):
    telegram_id = 3004
    live_backend.provider(telegram_id)

    state = DummyState()
    asyncio.run(dashboard.recevoir_nom_service_manquant(DummyMessage(telegram_id, text="Service exotique"), state))
    assert state.state == dashboard.ProviderServiceRequest.description

    message = DummyMessage(telegram_id, text="Description suffisamment longue pour passer la validation.")
    asyncio.run(dashboard.recevoir_description_service_manquant(message, state))

    assert state.cleared is True
    assert _requests(live_backend, telegram_id) == [("Service exotique", "pending")]
    assert "SRV-" in message.answers[-1]


def test_service_request_keeps_the_step_open_when_the_backend_is_down():
    """Rien n'est enregistré nulle part : la personne renvoie sa description."""
    state = DummyState({"missing_service_name": "Service exotique"})
    message = DummyMessage(3011, text="Description suffisamment longue pour passer la validation.")
    asyncio.run(dashboard.recevoir_description_service_manquant(message, state))

    assert state.cleared is False
    assert state._data["missing_service_name"] == "Service exotique"
    assert "indisponible" in message.answers[-1]


# --- missions / wallet client ---------------------------------------------


def test_afficher_missions_client_shows_empty_state(live_backend):
    telegram_id = 3005
    live_backend.client(telegram_id)

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_client(callback))

    assert callback.message.edited_text == get_message("missions_empty", "fr")


def test_afficher_missions_client_lists_the_backend_missions(live_backend):
    telegram_id = 3006
    live_backend.client(telegram_id)
    mission_id = live_backend.new_mission(telegram_id, service="service_plomberie")
    live_backend.new_mission(3999)  # mission d'un autre client : jamais montrée

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_client(callback))

    assert f"NXH-{mission_id:04d}" in callback.message.edited_text
    assert callback.message.edited_text.count("NXH-") == 1


def test_afficher_missions_client_says_unavailable_when_the_backend_is_down():
    callback = DummyCallback(3016)
    asyncio.run(dashboard.afficher_missions_client(callback))

    assert callback.answered == get_message("service_unavailable", "fr")
    assert callback.message.edited_text is None


# --- missions / wallet prestataire -----------------------------------------


def test_afficher_missions_prestataire_shows_empty_state(live_backend):
    telegram_id = 3008
    live_backend.provider(telegram_id)

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_prestataire(callback))

    assert callback.message.edited_text == get_message("provider_missions_empty", "fr")


def test_afficher_missions_prestataire_lists_the_missions_entrusted_to_them(live_backend):
    telegram_id, client_id = 3009, 3109
    entrusted, _ = live_backend.accepted_quote(client_id, telegram_id, service="service_electricite")
    live_backend.quoted_mission(client_id, telegram_id)  # devis pas encore accepté : pas confiée

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_missions_prestataire(callback))

    assert f"NXH-{entrusted:04d}" in callback.message.edited_text
    assert callback.message.edited_text.count("NXH-") == 1


def test_afficher_wallet_client_reads_the_registry(live_backend):
    """Le registre du backend est la seule source des soldes."""
    telegram_id = 3012
    live_backend.client(telegram_id)
    live_backend.credit_wallet(telegram_id, 42.5)
    live_backend.credit_wallet(telegram_id, 7000.0, currency="CDF")

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_client(callback))

    assert "42.50 USD" in callback.message.edited_text
    assert "7000.00 CDF" in callback.message.edited_text


def test_afficher_wallet_client_shows_unavailable_when_the_backend_is_down():
    callback = DummyCallback(3013)
    asyncio.run(dashboard.afficher_wallet_client(callback))

    assert callback.message.edited_text == get_message("wallet_unavailable", "fr")


def test_client_and_provider_screens_show_the_same_single_wallet(live_backend):
    telegram_id = 3014
    live_backend.client(telegram_id)
    live_backend.provider(telegram_id)
    live_backend.credit_wallet(telegram_id, 88.0)

    provider_callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_prestataire(provider_callback))
    client_callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_wallet_client(client_callback))

    assert "88.00 USD" in provider_callback.message.edited_text
    assert "88.00 USD" in client_callback.message.edited_text


def test_afficher_wallet_prestataire_shows_unavailable_when_the_backend_is_down():
    callback = DummyCallback(3015)
    asyncio.run(dashboard.afficher_wallet_prestataire(callback))

    assert callback.message.edited_text == get_message("wallet_unavailable", "fr")


# --- historique / aide ------------------------------------------------------


def test_afficher_historique_client_filters_terminal_statuses_only(live_backend):
    client_id, provider_id = 3009, 3109
    live_backend.client(client_id)

    live_backend.new_mission(client_id)  # mission active : pas dans l'historique
    mission_id = live_backend.completed_mission(client_id, provider_id, amount=50.0, service="service_electricite")

    callback = DummyCallback(client_id)
    asyncio.run(dashboard.afficher_historique_client(callback))

    assert callback.message.edited_text is not None
    assert f"NXH-{mission_id:04d}" in callback.message.edited_text
    assert callback.message.edited_text.count("NXH-") == 1, "seule la mission terminale doit apparaître dans l'historique"


def test_afficher_historique_client_shows_empty_state_when_nothing_terminal(live_backend):
    telegram_id = 3010
    live_backend.client(telegram_id)
    live_backend.new_mission(telegram_id)

    callback = DummyCallback(telegram_id)
    asyncio.run(dashboard.afficher_historique_client(callback))

    assert callback.message.edited_text == get_message("mission_history_empty", "fr")


def test_afficher_aide_client_falls_back_to_plain_text():
    callback = DummyCallback(3011)
    asyncio.run(dashboard.afficher_aide_client(callback))

    assert callback.message.edited_text is not None
