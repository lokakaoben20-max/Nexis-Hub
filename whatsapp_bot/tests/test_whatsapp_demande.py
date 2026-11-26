"""Service WhatsApp, étape 5 : créer une mission pas à pas.

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis). Chaque test parle au service comme un client WhatsApp et vérifie ce
que le backend a réellement enregistré.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from messages import get_message
from whatsapp_bot import demande, meta
from whatsapp_bot.fake_meta import DEFAULT_BSUID
from whatsapp_bot.tests.conftest import publish_terms, run, verified_provider

# Inscription WhatsApp et création de mission exigent la case des conditions.
pytestmark = pytest.mark.conditions_reelles

GOMBE = (-4.3076, 15.3125)
PARIS = (48.8566, 2.3522)
LANDMARK = "Portail bleu après la poste"
DESCRIPTION = "Nettoyer le salon et la cuisine, samedi matin."


def _missions(main):
    from backend.app.models import BotMission

    with main.database.SessionLocal() as db:
        return db.execute(select(BotMission).order_by(BotMission.mission_id)).scalars().all()


def _alerts(main):
    from backend.app.models import Notification

    with main.database.SessionLocal() as db:
        return db.execute(select(Notification).where(Notification.message_key == "new_mission_alert")).scalars().all()


def _whatsapp_account(main, bsuid=DEFAULT_BSUID):
    from backend.app import ledger

    with main.database.SessionLocal() as db:
        return ledger.account_id_for(db, ledger.WHATSAPP, bsuid)


async def _up_to_recap(bench, *, urgent=True, currency="USD", place=GOMBE):
    """Toutes les réponses jusqu'au récapitulatif ; rend ce que le service a
    envoyé à chaque étape."""
    steps = {}
    steps["services"] = await bench.tap("menu:new_request")
    steps["urgent"] = await bench.tap("svc:service_nettoyage")
    steps["communes"] = await bench.tap(demande.URGENT_YES if urgent else demande.URGENT_NO)
    steps["location"] = await bench.tap("com:Gombe")
    steps["landmark"] = await bench.locate(*place)
    steps["currency"] = await bench.say(LANDMARK)
    steps["description"] = await bench.tap(f"m:cur:{currency}")
    steps["recap"] = await bench.say(DESCRIPTION)
    return steps


def _choices(sent) -> list[str]:
    return [choice_id for message in sent for choice_id, _title in message.choices]


def test_a_whatsapp_client_creates_a_mission_step_by_step(bench):
    provider_account = verified_provider(bench.main)

    async def scenario():
        async with bench:
            menu = (await bench.register())[-1]
            assert "menu:new_request" in _choices([menu])
            steps = await _up_to_recap(bench)

            services = steps["services"][-1]
            assert services.kind == "list"
            # Le catalogue du backend, sans « Autre service » (qui part à l'équipe).
            assert "svc:service_nettoyage" in _choices([services])
            assert "svc:service_autre" not in _choices([services])
            assert "Nettoyage" in steps["urgent"][-1].text
            assert steps["communes"][-1].kind == "list"
            assert "com:Gombe" in _choices(steps["communes"])
            assert [message.kind for message in steps["location"]] == ["location_request_message", "button"]
            assert "repère" in steps["landmark"][-1].text
            assert _choices(steps["currency"]) == ["m:cur:USD", "m:cur:CDF", demande.BACK]
            recap = steps["recap"][-1]
            assert _choices([recap]) == [demande.CONFIRM, demande.EDIT, demande.CANCEL]
            for shown in ("Nettoyage", "Gombe", LANDMARK, "USD", DESCRIPTION, "Oui"):
                assert shown in recap.text
            assert _missions(bench.main) == []  # rien avant « Confirmer »

            saved = await bench.tap(demande.CONFIRM)
            assert "NXH-0001" in saved[0].text
            assert get_message("wa_matching_notified", "fr", count=1) in saved[0].text
            assert saved[-1].kind == "list"  # retour au menu
            return await bench.store.conversation(DEFAULT_BSUID)

    assert run(scenario) == {}
    (mission,) = _missions(bench.main)
    assert (mission.service, mission.commune, mission.currency, mission.urgent) == ("service_nettoyage", "Gombe", "USD", True)
    assert (mission.description, mission.destination_landmark) == (DESCRIPTION, LANDMARK)
    assert (mission.destination_latitude, mission.destination_longitude) == GOMBE
    assert mission.telegram_id is None
    assert mission.client_account_id == _whatsapp_account(bench.main)
    assert [alert.recipient_account_id for alert in _alerts(bench.main)] == [provider_account]


def test_the_same_answers_give_the_same_mission_as_telegram(bench):
    """Parité : la même demande faite sur Telegram (même corps que
    telegram_bot.backend_client.create_mission) donne la même mission."""
    from fastapi.testclient import TestClient

    from whatsapp_bot.tests.conftest import TELEGRAM_KEY

    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench, urgent=False, currency="CDF")
            await bench.tap(demande.CONFIRM)

    run(scenario)
    headers = {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": "42"}
    terms = {"surface": "telegram_bot", "documents": [{"document_key": "cgu", "version": "2026-11-20"}]}
    with TestClient(bench.main.app) as api:
        assert api.put("/api/me/client-profile", json={"first_name": "Mado", "terms": terms}, headers=headers).status_code == 200
        body = {
            "creation_key": "telegram-1",
            "service": "service_nettoyage",
            "commune": "Gombe",
            "currency": "CDF",
            "description": DESCRIPTION,
            "urgent": False,
            "media": [],
            "destination": {"latitude": GOMBE[0], "longitude": GOMBE[1], "landmark": LANDMARK},
        }
        assert api.post("/api/bot/missions", json=body, headers=headers).status_code == 200

    def fields(mission):
        return (
            mission.service, mission.commune, mission.currency, mission.description, mission.urgent, mission.status,
            mission.destination_latitude, mission.destination_longitude, mission.destination_landmark,
        )

    on_whatsapp, on_telegram = _missions(bench.main)
    assert fields(on_whatsapp) == fields(on_telegram)


def test_back_goes_to_the_previous_question_and_keeps_the_answers(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            await bench.tap(demande.URGENT_YES)
            # Commune → Retour : de nouveau l'urgence.
            back = await bench.tap(demande.BACK)
            assert _choices(back) == [demande.URGENT_YES, demande.URGENT_NO, demande.BACK]
            await bench.tap(demande.URGENT_NO)
            await bench.tap("com:Gombe")
            # Lieu → Retour : de nouveau les communes.
            back = await bench.tap(demande.BACK)
            assert "com:Gombe" in _choices(back)
            await bench.tap("com:Gombe")
            await bench.locate(*GOMBE)
            await bench.say(LANDMARK)
            await bench.tap("m:cur:USD")
            # Description → Retour : de nouveau la devise.
            back = await bench.tap(demande.BACK)
            assert _choices(back)[:2] == ["m:cur:USD", "m:cur:CDF"]
            await bench.tap("m:cur:CDF")
            recap = (await bench.say(DESCRIPTION))[-1]
            assert "CDF" in recap.text and get_message("wa_btn_no", "fr") in recap.text
            await bench.tap(demande.CONFIRM)

    run(scenario)
    (mission,) = _missions(bench.main)
    assert (mission.urgent, mission.currency) == (False, "CDF")


@pytest.mark.parametrize("how", ["button", "word"])
def test_cancel_stops_everything_and_creates_nothing(bench, how):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            await bench.tap(demande.URGENT_YES)
            await bench.tap("com:Gombe")
            sent = await (bench.tap(demande.CANCEL) if how == "button" else bench.say("Menu"))
            assert sent[0].text == get_message("wa_request_cancelled", "fr")
            assert sent[-1].kind == "list"
            assert await bench.store.conversation(DEFAULT_BSUID) == {}

    run(scenario)
    assert _missions(bench.main) == []


def test_cancel_from_the_recap_creates_nothing(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            await bench.tap(demande.CANCEL)
            # Un ancien bouton « Confirmer » après l'annulation : le menu, rien d'autre.
            stale = await bench.tap(demande.CONFIRM)
            assert [message.kind for message in stale] == ["list"]

    run(scenario)
    assert _missions(bench.main) == []


def test_edit_starts_again_from_the_service(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            again = await bench.tap(demande.EDIT)
            assert "svc:service_nettoyage" in _choices(again)
            return await bench.store.conversation(DEFAULT_BSUID)

    state = run(scenario)
    assert state["step"] == demande.SERVICE and state["draft"] == {}
    assert _missions(bench.main) == []


def test_a_place_outside_kinshasa_is_asked_again_and_the_rest_is_kept(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench, place=PARIS)
            refused = await bench.tap(demande.CONFIRM)
            assert refused[0].text == get_message("wa_destination_refused", "fr")
            assert refused[1].kind == "location_request_message"
            assert _missions(bench.main) == []
            await bench.locate(*GOMBE)
            # Après le repère, directement le récapitulatif (devise et description gardées).
            recap = (await bench.say("Immeuble vert, 3e étage"))[-1]
            assert _choices([recap]) == [demande.CONFIRM, demande.EDIT, demande.CANCEL]
            assert DESCRIPTION in recap.text
            await bench.tap(demande.CONFIRM)

    run(scenario)
    (mission,) = _missions(bench.main)
    assert (mission.destination_latitude, mission.destination_landmark) == (GOMBE[0], "Immeuble vert, 3e étage")


def test_the_place_must_be_a_shared_location_not_text_or_a_photo(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            await bench.tap(demande.URGENT_YES)
            await bench.tap("com:Gombe")
            typed = await bench.say("Avenue du Commerce 12")
            assert typed[0].text == get_message("wa_location_required", "fr")
            assert typed[1].kind == "location_request_message"
            photo = await bench.send_media("image")
            assert photo[0].text == get_message("wa_location_required", "fr")
            return await bench.store.conversation(DEFAULT_BSUID)

    assert run(scenario)["step"] == demande.LOCATION


def test_the_landmark_and_description_are_checked(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            await bench.tap(demande.URGENT_YES)
            await bench.tap("com:Gombe")
            await bench.locate(*GOMBE)
            assert (await bench.say("ok"))[0].text == get_message("wa_landmark_invalid", "fr")
            await bench.say(LANDMARK)
            await bench.tap("m:cur:USD")
            voice = await bench.send_media("audio")
            assert voice[0].text == get_message("wa_description_text_only", "fr")
            assert (await bench.say("ab"))[0].text == get_message("wa_description_invalid", "fr")
            recap = (await bench.say(DESCRIPTION))[-1]
            assert DESCRIPTION in recap.text

    run(scenario)


def test_a_double_tap_on_confirm_creates_one_mission(bench):
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            state = await bench.store.conversation(DEFAULT_BSUID)
            first = await bench.tap(demande.CONFIRM)
            # Second appui traité après le premier : la demande est finie, le menu.
            second = await bench.tap(demande.CONFIRM)
            assert "NXH-0001" in first[0].text
            assert [message.kind for message in second] == ["list"]
            # Même si l'étape était encore là (Redis rétabli d'une sauvegarde) :
            # même demande, même mission.
            await bench.store.save_conversation(DEFAULT_BSUID, state)
            third = await bench.tap(demande.CONFIRM)
            assert "NXH-0001" in third[0].text

    run(scenario)
    assert len(_missions(bench.main)) == 1
    assert len(_alerts(bench.main)) == 1


def test_a_replayed_confirm_after_a_lost_answer_creates_one_mission(bench):
    """Meta refuse l'envoi de la réponse : le message n'est pas noté fait,
    Meta renvoie le même webhook, le backend rend la même mission."""
    verified_provider(bench.main)

    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            payload = bench.fake.choice_message(demande.CONFIRM)
            bench.fake.fail_next("server")
            assert (await bench.post(payload)).status_code == 500
            assert len(_missions(bench.main)) == 1
            assert (await bench.post(payload)).status_code == 200
            assert "NXH-0001" in bench.fake.sent[-2].text

    run(scenario)
    assert len(_missions(bench.main)) == 1
    assert len(_alerts(bench.main)) == 1


def test_backend_down_at_confirm_keeps_the_request_to_try_again(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            bench.backend_down = True
            down = await bench.tap(demande.CONFIRM)
            assert down[0].text == get_message("service_unavailable", "fr")
            bench.backend_down = False
            # L'étape est gardée : un nouvel appui sur « Confirmer » suffit.
            assert "NXH-0001" in (await bench.tap(demande.CONFIRM))[0].text

    run(scenario)
    assert len(_missions(bench.main)) == 1


def test_new_terms_are_accepted_then_the_request_is_confirmed(bench):
    from datetime import datetime, timedelta, timezone

    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            publish_terms(bench.main, "2026-12-01", at=now, documents=("cgu",))
            asked = await bench.tap(demande.CONFIRM)
            assert _choices(asked[-1:]) == [demande.TERMS_ACCEPT, demande.TERMS_DECLINE]
            assert "2026-12-01" in asked[-1].text
            assert _missions(bench.main) == []
            recap = (await bench.tap(demande.TERMS_ACCEPT))[-1]
            assert _choices([recap]) == [demande.CONFIRM, demande.EDIT, demande.CANCEL]
            assert "NXH-0001" in (await bench.tap(demande.CONFIRM))[0].text

    run(scenario)
    assert len(_missions(bench.main)) == 1


def test_declining_new_terms_creates_nothing(bench):
    from datetime import datetime, timedelta, timezone

    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            now = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=1)
            publish_terms(bench.main, "2026-12-01", at=now, documents=("cgu",))
            await bench.tap(demande.CONFIRM)
            declined = await bench.tap(demande.TERMS_DECLINE)
            assert declined[0].text == get_message("wa_terms_update_declined", "fr")

    run(scenario)
    assert _missions(bench.main) == []


def test_an_old_menu_entry_leaves_the_request(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            help_text = await bench.tap("menu:help")
            assert help_text[0].text == get_message("wa_help", "fr")
            return await bench.store.conversation(DEFAULT_BSUID)

    assert run(scenario) == {}


def test_a_button_from_another_step_repeats_the_current_question(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            # Une ancienne ligne de service alors que l'urgence est demandée.
            again = await bench.tap("com:Gombe")
            assert _choices(again) == [demande.URGENT_YES, demande.URGENT_NO, demande.BACK]
            return await bench.store.conversation(DEFAULT_BSUID)

    assert run(scenario)["step"] == demande.URGENT


def test_a_service_removed_from_the_catalogue_is_refused(bench):
    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            refused = await bench.tap("svc:service_inconnu")
            assert refused[0].text == get_message("wa_catalogue_changed", "fr")
            assert refused[-1].kind == "list"

    run(scenario)


@pytest.mark.parametrize("lang", ["fr", "ln", "en"])
def test_every_mission_screen_respects_whatsapp_limits(bench, lang):
    """Chaque écran passe les limites vérifiées par meta.py et par le faux
    Meta (sinon l'envoi échouerait), dans chaque langue."""

    async def scenario():
        async with bench:
            await bench.register(language=lang)
            steps = await _up_to_recap(bench)
            for sent in steps.values():
                for message in sent:
                    assert message.kind in ("text", "button", "list", "location_request_message")
            await bench.tap(demande.CONFIRM)

    run(scenario)
    assert len(_missions(bench.main)) == 1


def test_a_long_description_is_shortened_on_screen_only(bench):
    long_description = "Fuite importante. " * 150  # ~2 700 caractères

    async def scenario():
        async with bench:
            await bench.register()
            await bench.tap("menu:new_request")
            await bench.tap("svc:service_nettoyage")
            await bench.tap(demande.URGENT_YES)
            await bench.tap("com:Gombe")
            await bench.locate(*GOMBE)
            await bench.say(LANDMARK)
            await bench.tap("m:cur:USD")
            recap = (await bench.say(long_description))[-1]
            assert len(recap.text) <= meta.MAX_INTERACTIVE_BODY
            await bench.tap(demande.CONFIRM)

    run(scenario)
    (mission,) = _missions(bench.main)
    assert mission.description == long_description.strip()


def test_the_list_pages_when_there_are_more_than_ten_choices():
    rows = [(f"com:C{index}", f"Commune {index}", "") for index in range(24)]
    extra = ((demande.BACK, "↩️ Retour", ""),)
    seen = []
    page = 0
    for _ in range(4):
        menu = demande._list("Communes ?", "Communes", rows, extra, page, "fr")
        menu.payload()  # limites de WhatsApp
        ids = [row[0] for row in menu.rows]
        assert len(ids) <= meta.MAX_LIST_ROWS and ids[-1] == demande.BACK
        seen += [row_id for row_id in ids if row_id.startswith("com:")]
        page = demande._page(next(row_id for row_id in ids if row_id.startswith(demande.PAGE_ROW)))
    # Les 24 communes, chacune une fois, puis retour à la première page.
    assert seen[:24] == [row[0] for row in rows] and page in (0, 1)


def test_no_position_or_text_of_the_request_reaches_the_logs(bench, caplog, monkeypatch):
    import logging

    for name in ("whatsapp_bot.app", "whatsapp_bot.conversation", "whatsapp_bot.demande", "whatsapp_bot.meta", "httpx"):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)
    caplog.set_level(logging.DEBUG)

    async def scenario():
        async with bench:
            await bench.register()
            await _up_to_recap(bench)
            await bench.tap(demande.CONFIRM)

    run(scenario)
    logs = caplog.text
    for secret in (str(GOMBE[0]), str(GOMBE[1]), LANDMARK, DESCRIPTION, DEFAULT_BSUID):
        assert secret not in logs
    # Les journaux ont bien été lus (sinon le test ne prouverait rien).
    assert "/api/bot/missions" in logs
