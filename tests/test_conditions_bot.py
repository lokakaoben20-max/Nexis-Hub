"""La case des conditions d'utilisation dans le bot Telegram, contre le vrai
backend (telegram_bot/conditions.py, telegram_bot/registration.py).

Inscription client et prestataire, bascule client -> prestataire : la case
est le dernier écran, rien n'est créé sans elle. Nouvelle version : le filtre
montre la case avant toute nouvelle action, laisse passer le reste.
"""

import asyncio
import os

import pytest

os.environ.setdefault("BOT_TOKEN", "123:ABC")

from aiogram.types import CallbackQuery, Chat, Message, User  # noqa: E402
from sqlalchemy import select  # noqa: E402

from backend.app import conditions as regles  # noqa: E402
from telegram_bot import backend_client, registration  # noqa: E402
from telegram_bot import conditions as case  # noqa: E402

pytestmark = pytest.mark.conditions_reelles


class Person:
    def __init__(self, telegram_id, first_name="Laura"):
        self.id = telegram_id
        self.first_name = first_name
        self.language_code = "fr"


class Contact:
    def __init__(self, user_id, phone_number):
        self.user_id = user_id
        self.phone_number = phone_number


class Chat_:
    def __init__(self, chat_id):
        self.id = chat_id


class Screen:
    """Message du bot : ce qu'il affiche et ses boutons."""

    def __init__(self, chat_id):
        self.chat = Chat_(chat_id)
        self.answers = []

    async def answer(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def edit_text(self, text, parse_mode=None, reply_markup=None):
        self.answers.append((text, reply_markup))

    async def edit_reply_markup(self, reply_markup=None):
        self.answers.append((None, reply_markup))

    def last_text(self):
        return next(text for text, _ in reversed(self.answers) if text is not None)

    def buttons(self):
        markup = next(markup for _, markup in reversed(self.answers) if markup is not None and hasattr(markup, "inline_keyboard"))
        return [button for row in markup.inline_keyboard for button in row]


class ContactMessage(Screen):
    def __init__(self, telegram_id, phone_number):
        super().__init__(telegram_id)
        self.from_user = Person(telegram_id)
        self.contact = Contact(telegram_id, phone_number)


class Callback:
    def __init__(self, telegram_id, data, message=None):
        self.from_user = Person(telegram_id)
        self.data = data
        self.message = message or Screen(telegram_id)
        self.alert = None

    async def answer(self, text=None, show_alert=False):
        self.alert = text


class State:
    def __init__(self, data=None):
        self._data = dict(data or {})
        self.state = None
        self.cleared = False

    async def get_data(self):
        return dict(self._data)

    async def update_data(self, **kwargs):
        self._data.update(kwargs)

    async def set_state(self, state):
        self.state = state

    async def clear(self):
        self.cleared = True
        self.state = None
        self._data = {}


@pytest.fixture(autouse=True)
def _fresh_cache():
    case._complete_until.clear()
    yield
    case._complete_until.clear()


def publish(live, key, version):
    with live.database.SessionLocal() as db:
        regles.publish_version(db, key, version, f"Texte {key} {version}. " + "Article. " * 600)
        db.commit()


@pytest.fixture
def published(live_backend):
    publish(live_backend, "cgu", "v1")
    publish(live_backend, "conditions_prestataires", "v1")
    return live_backend


def acceptances(live):
    with live.database.SessionLocal() as db:
        rows = db.scalars(select(regles.LegalAcceptance).order_by(regles.LegalAcceptance.id)).all()
        return [(row.role, row.surface, row.language) for row in rows]


def run(coro):
    return asyncio.run(coro)


# --- Inscription client --------------------------------------------------------------


def test_a_client_signup_ends_with_the_box_and_nothing_exists_before_it(published):
    message = ContactMessage(601, "+243810000601")
    state = State({"language": "ln"})
    run(registration.enregistrer_client(message, state))

    assert state.state == registration.ClientRegistration.terms
    assert published.profile(601)["client"] is None, "rien n'est créé avant la case"
    assert "Mibeko ya kosalela Nexis Hub (CGU)" in message.last_text()
    labels = [button.text for button in message.buttons()]
    assert labels[-2:] == ["☐ Natangi mpe nandimi", "✅ Kokokisa"]

    # Valider sans cocher : refusé, rien n'est créé.
    validate = Callback(601, "terms_signup_ok", message)
    run(registration.valider_inscription_client(validate, state))
    assert validate.alert == "Fina liboso na kare « Natangi mpe nandimi »."
    assert published.profile(601)["client"] is None

    run(registration.cocher_case_inscription(Callback(601, "terms_signup_tick", message), state))
    assert message.buttons()[-2].text == "☑️ Natangi mpe nandimi"
    run(registration.valider_inscription_client(Callback(601, "terms_signup_ok", message), state))

    me = published.profile(601)
    assert (me["client"]["phone_number"], me["language"]) == ("+243810000601", "ln")
    assert acceptances(published) == [("client", "telegram_bot", "ln")]
    assert state.cleared is True


def test_a_version_changed_while_the_box_was_shown_is_shown_again(published):
    message = ContactMessage(602, "+243810000602")
    state = State({"language": "fr"})
    run(registration.enregistrer_client(message, state))
    run(registration.cocher_case_inscription(Callback(602, "terms_signup_tick", message), state))
    publish(published, "cgu", "v2")

    run(registration.valider_inscription_client(Callback(602, "terms_signup_ok", message), state))

    assert published.profile(602)["client"] is None
    assert acceptances(published) == []
    assert any("viennent d'être mises à jour" in text for text, _ in message.answers if text)
    assert state._data["terms_documents"][0]["version"] == "v2"
    assert state._data["terms_ticked"] is False, "la nouvelle version se coche de nouveau"


def test_nothing_published_means_no_signup_and_the_step_stays_open(live_backend):
    message = ContactMessage(603, "+243810000603")
    state = State({"language": "fr"})
    run(registration.enregistrer_client(message, state))

    assert "pas encore ouvertes" in message.last_text()
    assert state.state is None and "client_phone" not in state._data
    assert live_backend.profile(603)["client"] is None


# --- Inscription prestataire et bascule ------------------------------------------------


def provider_state(**extra):
    return State(
        {
            "provider_phone": "+243810000700",
            "provider_full_name": "Jean Mukendi",
            "provider_services": ["service_plomberie"],
            "provider_communes": ["Gombe"],
            "provider_id_document_file_id": "photo-id",
            "provider_selfie_file_id": "photo-selfie",
            "provider_portfolio_file_ids": [],
            "language": "fr",
            **extra,
        }
    )


def test_a_client_who_becomes_a_provider_ticks_only_the_provider_terms(published):
    message = ContactMessage(700, "+243810000700")
    state = State({"language": "fr"})
    run(registration.enregistrer_client(message, state))
    run(registration.cocher_case_inscription(Callback(700, "terms_signup_tick", message), state))
    run(registration.valider_inscription_client(Callback(700, "terms_signup_ok", message), state))

    state = provider_state()
    done = Callback(700, "provider_portfolio_done")
    run(registration.finaliser_inscription_prestataire(done, state))
    assert state.state == registration.ProviderRegistration.terms
    assert published.profile(700)["provider"] is None
    text = done.message.last_text()
    assert "Conditions des prestataires" in text and "Conditions générales" not in text

    run(registration.cocher_case_inscription(Callback(700, "terms_signup_tick", done.message), state))
    run(registration.valider_inscription_prestataire(Callback(700, "terms_signup_ok", done.message), state))
    assert published.profile(700)["provider"]["status"] == "pending_verification"
    assert [row[0] for row in acceptances(published)] == ["client", "provider"]


def test_a_new_provider_ticks_both_documents(published):
    state = provider_state()
    done = Callback(701, "provider_portfolio_done")
    run(registration.finaliser_inscription_prestataire(done, state))
    assert [item["document_key"] for item in state._data["terms_documents"]] == ["cgu", "conditions_prestataires"]
    run(registration.cocher_case_inscription(Callback(701, "terms_signup_tick", done.message), state))
    run(registration.valider_inscription_prestataire(Callback(701, "terms_signup_ok", done.message), state))
    assert published.profile(701)["provider"] is not None
    assert acceptances(published) == [("provider", "telegram_bot", "fr"), ("provider", "telegram_bot", "fr")]


# --- Le filtre devant les nouvelles actions -------------------------------------------


def callback_event(telegram_id, data):
    user = User(id=telegram_id, is_bot=False, first_name="Marie", language_code="fr")
    return CallbackQuery.model_construct(id="1", from_user=user, chat_instance="c", data=data, message=None), user


def message_event(telegram_id, text):
    user = User(id=telegram_id, is_bot=False, first_name="Marie", language_code="fr")
    chat = Chat(id=telegram_id, type="private")
    return Message.model_construct(message_id=1, date=0, chat=chat, from_user=user, text=text), user


@pytest.fixture
def answered(monkeypatch):
    """Réponses du filtre (alerte sur un bouton, message sinon)."""
    said = []

    async def callback_answer(self, text=None, show_alert=False, **kwargs):
        said.append(text)

    async def message_answer(self, text, parse_mode=None, reply_markup=None, **kwargs):
        said.append((text, reply_markup))

    monkeypatch.setattr(CallbackQuery, "answer", callback_answer)
    monkeypatch.setattr(Message, "answer", message_answer)
    return said


def through_gate(event, user, state=None, raw_state=None):
    ran = []

    async def handler(event, data):
        ran.append(event)
        return "fait"

    data = {"event_from_user": user, "state": state or State(), "raw_state": raw_state}
    result = run(case.ConditionsGate()(handler, event, data))
    return bool(ran), result


def test_a_new_action_waits_for_the_new_box_and_the_rest_goes_through(published, answered):
    published.client(42)  # client d'avant la règle : rien de coché
    state = State()
    event, user = message_event(42, "bonjour")
    ran, _ = through_gate(event, user, state)
    assert ran is False
    text, markup = answered[-1]
    assert "Nouvelles conditions" in text
    assert state._data["terms_role"] == "client"

    for data in ("client_wallet", "presence_yes_3", "wd_cur_USD", "admin_home", "lang_fr", "client_missions"):
        event, user = callback_event(42, data)
        assert through_gate(event, user)[0] is True, data
    event, user = callback_event(42, "client_demande")
    assert through_gate(event, user)[0] is False
    event, user = message_event(42, "/start")
    assert through_gate(event, user)[0] is True
    event, user = message_event(42, "Fuite sous l'évier")
    assert through_gate(event, user, raw_state="ClientRegistration:phone")[0] is True
    assert through_gate(event, user, raw_state="MissionRequest:description")[0] is False

    # Cocher puis valider : enregistré, l'action suivante passe.
    screen = Screen(42)
    run(case.confirm_again(Callback(42, "terms_again_ok", screen), state))
    assert acceptances(published) == []
    run(case.tick_again(Callback(42, "terms_again_tick", screen), state))
    run(case.confirm_again(Callback(42, "terms_again_ok", screen), state))
    assert acceptances(published) == [("client", "telegram_bot", "fr")]
    event, user = callback_event(42, "client_demande")
    assert through_gate(event, user)[0] is True


def test_a_backend_refusal_for_missing_terms_forgets_the_cached_answer(published, answered):
    published.client(43)
    from backend.app import ledger

    with published.database.SessionLocal() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, 43)
        regles.accept(db, account_id, "client", [{"document_key": "cgu", "version": "v1"}], surface="telegram_bot", language="fr")
        db.commit()
    event, user = callback_event(43, "client_demande")
    assert through_gate(event, user)[0] is True
    assert case._known_complete(43)

    publish(published, "cgu", "v2")
    with pytest.raises(backend_client.MoneyRefused) as refused:
        mission = {
            "service": "service_plomberie",
            "commune": "Gombe",
            "destination_latitude": -4.3076,
            "destination_longitude": 15.3125,
            "destination_landmark": "Portail bleu après la poste",
        }
        run(backend_client.create_mission(43, mission, "cle-1"))
    assert refused.value.code == "terms_not_accepted"
    assert not case._known_complete(43), "l'action suivante montre la case"
    assert through_gate(event, user)[0] is False


def test_the_gate_blocks_when_the_backend_cannot_say(answered):
    event, user = callback_event(44, "client_demande")
    ran, _ = through_gate(event, user)
    assert ran is False
    assert "indisponible" in answered[-1]


def test_the_gate_lets_a_person_without_a_role_through(published, answered):
    event, user = callback_event(45, "client_demande")
    assert through_gate(event, user)[0] is True


# --- Lire les textes -------------------------------------------------------------------


def test_the_read_button_opens_the_page_when_the_mini_app_has_an_address(monkeypatch):
    from telegram_bot import keyboards

    monkeypatch.setattr(keyboards, "MINI_APP_URL", "https://nexishub.dpdns.org/?vue=client")
    assert case.page_url("cgu", "v1", "ln") == "https://nexishub.dpdns.org/conditions/cgu/v1?lang=ln"
    monkeypatch.setattr(keyboards, "MINI_APP_URL", None)
    assert case.page_url("cgu", "v1", "fr") is None
    buttons = [button for row in case.keyboard("terms_again", [{"document_key": "cgu", "version": "v1"}], False, "fr").inline_keyboard for button in row]
    assert buttons[0].callback_data == "terms_read:cgu:v1"


def test_without_a_page_the_exact_text_is_sent_in_pieces(published):
    screen = Screen(46)
    run(case.read_document(Callback(46, "terms_read:cgu:v1", screen), State({"language": "fr"})))
    pieces = [text for text, _ in screen.answers]
    assert "version v1" in pieces[0]
    assert "".join(pieces[1:]).startswith("Texte cgu v1.")
    assert all(len(piece) <= case.CHUNK for piece in pieces[1:]) and len(pieces) > 2
