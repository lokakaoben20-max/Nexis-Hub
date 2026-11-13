"""Arrivée confirmée du prestataire (backend.app.presence).

Décisions de Ben du 8 novembre 2026 : la présence est confirmée par l'appui du
client (« Oui, il est là ») ou par le code de présence du client tapé par le
prestataire ; le « je suis arrivé » du prestataire seul ne confirme rien ; la
présence confirmée démarre la mission ; « Ce n'est pas lui » gèle la mission."""

import logging
from datetime import timedelta

import pytest

from backend.tests.test_main import _as, _register_provider
from backend.tests.test_mission_destination import _backend, _create, _pay, _quote

CLIENT = 42
PROVIDER = 7
OTHER_PROVIDER = 8
STRANGER = 555
ADMIN = 999


@pytest.fixture
def sent(monkeypatch):
    """Messages Telegram envoyés par le backend : (destinataire, texte, boutons)."""
    from backend.app import notify, tasks

    messages = []
    monkeypatch.setattr(notify, "send_telegram_message", lambda chat_id, text, reply_markup=None: messages.append((chat_id, text, reply_markup)) or True)
    monkeypatch.setattr(
        notify, "send_telegram_photo", lambda chat_id, file_id, caption, reply_markup=None: messages.append((chat_id, f"[photo {file_id}] {caption}", reply_markup)) or True
    )
    monkeypatch.setattr(tasks, "send_telegram_message", lambda chat_id, text, reply_markup=None: messages.append((chat_id, text, reply_markup)))
    monkeypatch.setattr(tasks, "ADMIN_TELEGRAM_ID", str(ADMIN))
    return messages


def _to(messages, chat_id):
    return [text for recipient, text, _ in messages if recipient == chat_id]


def _buttons(messages, chat_id):
    return [button["callback_data"] for recipient, _, markup in messages if recipient == chat_id and markup for row in markup["inline_keyboard"] for button in row]


def _paid_mission(test_client, database_module):
    _register_provider(test_client, PROVIDER, ["service_plomberie"], ["Gombe"], full_name="Jean Mukendi")
    _register_provider(test_client, OTHER_PROVIDER, ["service_plomberie"], ["Gombe"])
    mission_id = _create(test_client).json()["mission"]["mission_id"]
    quote_id = _quote(test_client, mission_id, PROVIDER)
    _quote(test_client, mission_id, OTHER_PROVIDER)
    assert test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(CLIENT)).status_code == 200
    _pay(test_client, database_module, mission_id, quote_id)
    return mission_id


def _post(test_client, mission_id, action, actor, **body):
    return test_client.post(f"/api/bot/missions/{mission_id}/presence/{action}", json=body or None, headers=_as(actor))


def _status(database_module, mission_id):
    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        return db.get(BotMission, mission_id).status


def _presence_row(database_module, mission_id):
    from backend.app.models import MissionPresence

    with database_module.SessionLocal() as db:
        rows = db.query(MissionPresence).filter_by(mission_id=mission_id).all()
        return rows[0] if len(rows) == 1 else rows


def _wrong(code):
    return "0000" if code != "0000" else "1111"


def test_the_presence_code_is_four_digits_stable_and_needs_a_key(monkeypatch):
    from backend.app import ledger, presence

    codes = {presence.presence_code(mission_id) for mission_id in range(1, 201)}
    assert all(len(code) == 4 and code.isdigit() for code in codes)
    assert presence.presence_code(12) == presence.presence_code(12)
    assert len(codes) > 150, "un code par mission, pas un code commun"

    monkeypatch.setenv("PRESENCE_CODE_KEY", "trop-courte")
    with pytest.raises(ledger.MoneyError) as refusal:
        presence.presence_code(12)
    assert (refusal.value.code, refusal.value.http_status) == ("presence_not_configured", 503)


def test_the_arrival_alone_starts_nothing_and_asks_the_client(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        code = presence.presence_code(mission_id)
        sent.clear()

        arrived = _post(test_client, mission_id, "arrived", PROVIDER)

    assert arrived.status_code == 200
    assert arrived.json()["mission"]["status"] == "confirmed"
    assert arrived.json()["client_asked"] is True
    assert arrived.json()["presence"]["confirmed"] is False
    assert "code" not in arrived.json()["presence"], "jamais le code au prestataire"
    assert _status(database_module, mission_id) == "confirmed"

    question = _to(sent, CLIENT)
    assert len(question) == 1
    assert f"<b>{code}</b>" in question[0]
    assert "Jean" in question[0] and "Mukendi" not in question[0], "le prénom seulement"
    assert _buttons(sent, CLIENT) == [f"presence_yes_{mission_id}", f"presence_notyet_{mission_id}", f"presence_wrong_{mission_id}"]
    assert _to(sent, PROVIDER) == [], "le prestataire voit la réponse dans son canal"


def test_the_question_shows_the_provider_photo_when_there_is_one(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app.models import BotProvider

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        with database_module.SessionLocal() as db:
            db.get(BotProvider, PROVIDER).selfie_file_id = "selfie-file-id"
            db.commit()
        sent.clear()
        _post(test_client, mission_id, "arrived", PROVIDER)

    assert _to(sent, CLIENT)[0].startswith("[photo selfie-file-id] ")


def test_the_question_still_leaves_when_telegram_refuses_the_photo(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import notify
    from backend.app.models import BotProvider

    monkeypatch.setattr(notify, "send_telegram_photo", lambda *args, **kwargs: False)
    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        with database_module.SessionLocal() as db:
            db.get(BotProvider, PROVIDER).selfie_file_id = "expired"
            db.commit()
        sent.clear()
        _post(test_client, mission_id, "arrived", PROVIDER)

    assert len(_to(sent, CLIENT)) == 1


def test_the_question_is_asked_again_only_after_a_while_or_a_not_yet(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app.models import MissionPresence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        sent.clear()
        assert _post(test_client, mission_id, "arrived", PROVIDER).json()["client_asked"] is True
        again = _post(test_client, mission_id, "arrived", PROVIDER)
        assert again.status_code == 200 and again.json()["client_asked"] is False
        assert len(_to(sent, CLIENT)) == 1, "le bouton ne sert pas à harceler le client"

        with database_module.SessionLocal() as db:
            row = db.get(MissionPresence, mission_id)
            row.client_asked_at -= timedelta(minutes=3)
            db.commit()
        assert _post(test_client, mission_id, "arrived", PROVIDER).json()["client_asked"] is True

        assert _post(test_client, mission_id, "not-yet", CLIENT).status_code == 200
        assert _post(test_client, mission_id, "not-yet", CLIENT).status_code == 200
        assert len(_to(sent, PROVIDER)) == 1, "une réponse rejouée ne prévient pas deux fois"
        assert _buttons(sent, PROVIDER) == [f"presence_arrived_{mission_id}", f"presence_code_{mission_id}", f"mission_place_{mission_id}"]
        assert _status(database_module, mission_id) == "confirmed", "« pas encore » ne change rien d'autre"

        assert _post(test_client, mission_id, "arrived", PROVIDER).json()["client_asked"] is True, "après « pas encore », on repose la question"
    assert len(_to(sent, CLIENT)) == 3


def test_the_client_tap_confirms_and_starts_the_mission_once(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        _post(test_client, mission_id, "arrived", PROVIDER)
        sent.clear()

        first = _post(test_client, mission_id, "confirm", CLIENT)
        replay = _post(test_client, mission_id, "confirm", CLIENT)

        assert first.status_code == replay.status_code == 200
        assert first.json()["mission"]["status"] == "in_progress"
        assert first.json()["presence"]["confirmed_by"] == "client"
        assert first.json()["presence"]["code"] is None, "plus de code une fois l'arrivée confirmée"
        assert _post(test_client, mission_id, "arrived", PROVIDER).json()["presence"]["confirmed"] is True

    assert _status(database_module, mission_id) == "in_progress"
    assert len(_to(sent, PROVIDER)) == 1, "un seul message, même rejoué"
    assert _buttons(sent, PROVIDER) == [f"mission_finish_{mission_id}", f"mission_place_{mission_id}"]
    assert _to(sent, CLIENT) == [], "le client voit la réponse dans son canal"


def test_the_presence_code_confirms_and_starts_the_mission(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        code = presence.presence_code(mission_id)
        sent.clear()

        badly_typed = _post(test_client, mission_id, "code", PROVIDER, code="12a4")
        wrong = _post(test_client, mission_id, "code", PROVIDER, code=_wrong(code))
        right = _post(test_client, mission_id, "code", PROVIDER, code=f" {code} ")

    assert badly_typed.status_code == 400 and badly_typed.json()["detail"]["code"] == "invalid_presence_code"
    assert wrong.status_code == 400
    assert wrong.json()["detail"]["code"] == "wrong_presence_code"
    assert wrong.json()["detail"]["attempts_left"] == 4, "le code mal formé n'est pas compté"
    assert right.status_code == 200
    assert right.json()["mission"]["status"] == "in_progress"
    assert right.json()["presence"]["confirmed_by"] == "presence_code"
    assert code not in str(right.json()), "le code n'est jamais renvoyé au prestataire"
    assert len(_to(sent, CLIENT)) == 1 and "démarré" in _to(sent, CLIENT)[0]
    assert _to(sent, PROVIDER) == []


def test_only_the_chosen_provider_can_use_the_code(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        code = presence.presence_code(mission_id)
        other = _post(test_client, mission_id, "code", OTHER_PROVIDER, code=code)
        client_typing = _post(test_client, mission_id, "code", CLIENT, code=code)
        stranger_tap = _post(test_client, mission_id, "confirm", STRANGER)
        provider_tap = _post(test_client, mission_id, "confirm", PROVIDER)

    assert other.json()["detail"]["code"] == "not_mission_provider"
    assert client_typing.json()["detail"]["code"] == "not_mission_provider"
    assert stranger_tap.status_code == 403
    assert provider_tap.json()["detail"]["code"] == "not_mission_client", "le « oui » du prestataire ne vaut rien"
    assert _status(database_module, mission_id) == "confirmed"


def test_five_wrong_codes_lock_the_code_and_alert_the_admin(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        code = presence.presence_code(mission_id)
        sent.clear()
        answers = [_post(test_client, mission_id, "code", PROVIDER, code=_wrong(code)) for _ in range(5)]
        sixth = _post(test_client, mission_id, "code", PROVIDER, code=code)
        state = test_client.get(f"/api/bot/missions/{mission_id}/presence", headers=_as(CLIENT)).json()["presence"]
        client_still_can = _post(test_client, mission_id, "confirm", CLIENT)

    assert [answer.json()["detail"]["code"] for answer in answers] == ["wrong_presence_code"] * 4 + ["presence_code_locked"]
    assert [answer.json()["detail"]["attempts_left"] for answer in answers] == [4, 3, 2, 1, 0]
    assert sixth.status_code == 403 and sixth.json()["detail"]["code"] == "presence_code_locked", "même le bon code, après 5 essais"
    assert state["code_locked"] is True and state["confirmed"] is False
    assert len(_to(sent, ADMIN)) == 1 and "5 mauvais codes" in _to(sent, ADMIN)[0]
    assert len(_to(sent, CLIENT)) == 1, "le client sait que seul son appui confirme"
    assert client_still_can.json()["mission"]["status"] == "in_progress"
    assert _presence_row(database_module, mission_id).failed_code_attempts == 5


def test_client_and_code_at_the_same_time_record_one_presence(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        sent.clear()
        by_client = _post(test_client, mission_id, "confirm", CLIENT)
        by_code = _post(test_client, mission_id, "code", PROVIDER, code=presence.presence_code(mission_id))

    assert by_client.status_code == by_code.status_code == 200
    assert by_code.json()["presence"]["confirmed_by"] == "client", "la première réponse valide fait foi"
    row = _presence_row(database_module, mission_id)
    assert row.confirmed_by == "client"
    assert len(_to(sent, PROVIDER)) == 1 and _to(sent, CLIENT) == []


def test_that_is_not_him_freezes_the_mission(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import ledger, presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        _post(test_client, mission_id, "arrived", PROVIDER)
        sent.clear()

        reported = _post(test_client, mission_id, "wrong-person", CLIENT)
        replay = _post(test_client, mission_id, "wrong-person", CLIENT)
        late_yes = _post(test_client, mission_id, "confirm", CLIENT)
        late_code = _post(test_client, mission_id, "code", PROVIDER, code=presence.presence_code(mission_id))
        finish = test_client.post(f"/api/bot/missions/{mission_id}/finish", headers=_as(PROVIDER))
        destination = test_client.get(f"/api/bot/missions/{mission_id}/destination", headers=_as(PROVIDER))

    assert reported.status_code == replay.status_code == 200
    assert reported.json()["mission"]["status"] == "disputed"
    assert reported.json()["presence"]["wrong_person_reported"] is True
    assert late_yes.json()["detail"]["code"] == "mission_disputed"
    assert late_code.json()["detail"]["code"] == "mission_disputed"
    assert finish.json()["detail"]["code"] == "mission_disputed"
    assert destination.status_code == 403, "le lieu n'est plus montré au prestataire"
    assert len(_to(sent, ADMIN)) == 1 and "Ce n'est pas lui" in _to(sent, ADMIN)[0]
    assert len(_to(sent, PROVIDER)) == 1
    with database_module.SessionLocal() as db:
        assert ledger.mission_operation(db, mission_id, ledger.SETTLEMENT) is None, "aucun argent ne bouge"
        assert "signalé par le client à l'arrivée" in db.get(ledger.BotMission, mission_id).dispute_reason


def test_another_client_cannot_answer(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        answers = [_post(test_client, mission_id, action, STRANGER) for action in ("confirm", "not-yet", "wrong-person")]

    assert [answer.status_code for answer in answers] == [403, 403, 403]
    assert _status(database_module, mission_id) == "confirmed"
    assert _presence_row(database_module, mission_id) == []


def test_nothing_happens_before_payment(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        _register_provider(test_client, PROVIDER, ["service_plomberie"], ["Gombe"])
        mission_id = _create(test_client).json()["mission"]["mission_id"]
        quote_id = _quote(test_client, mission_id, PROVIDER)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(CLIENT))
        sent.clear()

        arrived = _post(test_client, mission_id, "arrived", PROVIDER)
        confirmed = _post(test_client, mission_id, "confirm", CLIENT)
        wrong_person = _post(test_client, mission_id, "wrong-person", CLIENT)
        state = test_client.get(f"/api/bot/missions/{mission_id}/presence", headers=_as(CLIENT))

    assert arrived.json()["detail"]["code"] == "not_paid"
    assert confirmed.json()["detail"]["code"] == "not_paid"
    assert wrong_person.json()["detail"]["code"] == "not_paid"
    assert state.json()["presence"]["code"] is None, "pas de code avant le paiement"
    assert sent == []
    assert _presence_row(database_module, mission_id) == [], "un refus n'enregistre rien"


def test_who_reads_the_presence_and_the_code(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    with test_client:
        mission_id = _paid_mission(test_client, database_module)

        def read(actor):
            return test_client.get(f"/api/bot/missions/{mission_id}/presence", headers=_as(actor))

        client_view, provider_view, admin_view = read(CLIENT), read(PROVIDER), read(ADMIN)
        other_view, stranger_view = read(OTHER_PROVIDER), read(STRANGER)

    assert client_view.json()["presence"]["code"] == presence.presence_code(mission_id)
    assert "code" not in provider_view.json()["presence"]
    assert admin_view.status_code == 200 and "code" not in admin_view.json()["presence"]
    assert other_view.status_code == stranger_view.status_code == 404


def test_without_the_key_nothing_is_counted(backend_db_url, monkeypatch, sent):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        monkeypatch.setenv("PRESENCE_CODE_KEY", "")
        refused = _post(test_client, mission_id, "code", PROVIDER, code="1234")

    assert refused.status_code == 503 and refused.json()["detail"]["code"] == "presence_not_configured"
    assert _presence_row(database_module, mission_id) == []


def test_the_code_never_reaches_the_logs(backend_db_url, monkeypatch, sent, caplog):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    from backend.app import presence

    caplog.set_level(logging.DEBUG)
    with test_client:
        mission_id = _paid_mission(test_client, database_module)
        code = presence.presence_code(mission_id)
        caplog.clear()
        _post(test_client, mission_id, "arrived", PROVIDER)
        for _ in range(2):
            _post(test_client, mission_id, "code", PROVIDER, code=_wrong(code))
        _post(test_client, mission_id, "code", PROVIDER, code=code)

    assert code not in caplog.text


def test_the_presence_table_refuses_inconsistent_rows(backend_db_url, monkeypatch, sent):
    from sqlalchemy.exc import IntegrityError

    from backend.app.models import MissionPresence

    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        mission_id = _paid_mission(test_client, database_module)

    for fields in ({"confirmed_by": "client"}, {"failed_code_attempts": 6}, {"failed_code_attempts": 5}, {"confirmed_by": "provider", "confirmed_at": presence_now()}):
        with database_module.SessionLocal() as db:
            db.add(MissionPresence(mission_id=mission_id, **{"failed_code_attempts": 0, **fields}))
            with pytest.raises(IntegrityError):
                db.commit()


def presence_now():
    from datetime import datetime

    return datetime(2026, 11, 8, 12, 0)
