"""Flow inscription/profil (telegram_bot/registration.py) contre le vrai
backend : chaque lecture et chaque écriture de profil passe par lui, au nom de
la personne. Backend injoignable : la personne le voit, rien n'est écrit."""

import asyncio
import os

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from telegram_bot import registration


class DummyContact:
    def __init__(self, user_id, phone_number):
        self.user_id = user_id
        self.phone_number = phone_number


class DummyMessage:
    def __init__(self):
        self.edited_text = None
        self.reply_markup = None

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text
        self.reply_markup = reply_markup

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.edited_text = text
        self.reply_markup = reply_markup


class DummyUser:
    def __init__(self, telegram_id, first_name="Test"):
        self.id = telegram_id
        self.first_name = first_name


class DummyContactMessage:
    def __init__(self, telegram_id, phone_number, first_name="Laura"):
        self.from_user = DummyUser(telegram_id, first_name)
        self.contact = DummyContact(telegram_id, phone_number)
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append(text)


class DummyCallback:
    def __init__(self, telegram_id, data=""):
        self.from_user = DummyUser(telegram_id)
        self.data = data
        self.message = DummyMessage()
        self.answered = None

    async def answer(self, text=None, show_alert=False):
        self.answered = text


class DummyState:
    def __init__(self, data=None):
        self._data = data or {}
        self.cleared = False

    async def get_data(self):
        return self._data

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        self._data["_state"] = state

    async def clear(self):
        self.cleared = True
        self._data = {}




def test_terminer_inscription_prestataire_asks_for_documents_before_creating_provider(live_backend):
    """Vérification obligatoire : rien n'est envoyé au backend avant la pièce
    d'identité et le selfie (voir tests/test_provider_verification.py)."""
    callback = DummyCallback(telegram_id=501, data="provider_communes_done")
    state = DummyState(data={
        "provider_phone": "+243800000501",
        "provider_full_name": "Alice Prestataire",
        "provider_services": ["service_plomberie"],
        "provider_communes": ["Gombe"],
        "language": "fr",
    })

    asyncio.run(registration.terminer_inscription_prestataire(callback, state))

    assert live_backend.profile(501)["provider"] is None, "pas encore créé avant les documents"


def test_a_client_registers_with_the_shared_number(live_backend):
    message = DummyContactMessage(601, "+243810000601")
    state = DummyState(data={"language": "ln", "_state": "phone"})

    asyncio.run(registration.enregistrer_client(message, state))

    me = live_backend.profile(601)
    assert (me["client"]["first_name"], me["client"]["phone_number"], me["language"]) == ("Laura", "+243810000601", "ln")
    assert state.cleared is True


def test_a_client_registration_waits_when_the_backend_is_down():
    message = DummyContactMessage(601, "+243810000601")
    state = DummyState(data={"language": "fr", "_state": "phone"})

    asyncio.run(registration.enregistrer_client(message, state))

    assert state.cleared is False, "l'étape reste ouverte : la personne renvoie son numéro"
    assert "indisponible" in message.answers[-1]


def test_changer_disponibilite_writes_the_backend(live_backend):
    live_backend.provider(502)

    callback = DummyCallback(telegram_id=502, data="provider_status_offline")
    asyncio.run(registration.changer_disponibilite(callback))

    assert live_backend.profile(502)["provider"]["status"] == "offline"
    assert "Indisponible" in callback.message.edited_text


def test_changer_disponibilite_refused_while_awaiting_validation(live_backend):
    live_backend.provider(504, verified=False)

    callback = DummyCallback(telegram_id=504, data="provider_status_available")
    asyncio.run(registration.changer_disponibilite(callback))

    assert live_backend.profile(504)["provider"]["status"] == "pending_verification"
    assert "validation" in callback.answered
    assert live_backend.new_mission(42, service="service_plomberie") and live_backend.mission(1) is not None
    assert live_backend.alerted(1) == []


def test_changer_disponibilite_when_the_backend_is_down_changes_nothing():
    callback = DummyCallback(telegram_id=503, data="provider_status_available")
    asyncio.run(registration.changer_disponibilite(callback))

    assert "indisponible" in callback.answered
    assert callback.message.edited_text is None


def test_enregistrer_services_modifies_writes_the_backend(live_backend):
    live_backend.provider(504)

    callback = DummyCallback(telegram_id=504, data="edit_services_done")
    state = DummyState(data={"provider_services_edit": ["service_electricite", "service_informatique"], "language": "fr"})

    asyncio.run(registration.enregistrer_services_modifies(callback, state))

    assert live_backend.profile(504)["provider"]["services"] == ["service_electricite", "service_informatique"]
    assert state.cleared is True


def test_enregistrer_services_keeps_the_choice_when_the_backend_is_down():
    callback = DummyCallback(telegram_id=504, data="edit_services_done")
    state = DummyState(data={"provider_services_edit": ["service_electricite"], "language": "fr"})

    asyncio.run(registration.enregistrer_services_modifies(callback, state))

    assert state.cleared is False
    assert "indisponible" in callback.answered


def test_langue_fr_updates_the_account_language(live_backend):
    live_backend.client(505, language="en")

    callback = DummyCallback(telegram_id=505, data="lang_fr")
    state = DummyState()

    asyncio.run(registration.langue_fr(callback, state))

    assert live_backend.profile(505)["language"] == "fr"
    assert state._data["language"] == "fr"


def test_langue_for_a_new_person_is_kept_for_the_registration(live_backend):
    callback = DummyCallback(telegram_id=506, data="lang_ln")
    state = DummyState()

    asyncio.run(registration.langue_ln(callback, state))

    assert state._data["language"] == "ln"
    assert live_backend.profile(506)["profile_type"] == "guest"


def test_afficher_profil_client_reads_the_backend(live_backend):
    live_backend.client(507, first_name="Cliente", language="ln", phone="+243800000507")

    callback = DummyCallback(telegram_id=507, data="client_profil")
    asyncio.run(registration.afficher_profil_client(callback))

    assert "Cliente" in callback.message.edited_text
    assert "Lingala" in callback.message.edited_text
    assert "+243800000507" in callback.message.edited_text


def test_afficher_profil_client_says_when_the_backend_is_down():
    callback = DummyCallback(telegram_id=507, data="client_profil")
    asyncio.run(registration.afficher_profil_client(callback))

    assert callback.message.edited_text is None
    assert "indisponible" in callback.answered
