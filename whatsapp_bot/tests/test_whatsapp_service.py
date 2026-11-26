"""Service WhatsApp, étape 4 : webhook signé, chaque message traité une fois,
inscription, menu, refus prestataire, refus des médias, pannes.

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis)."""

from __future__ import annotations

import logging

import pytest
from sqlalchemy import select

from messages import get_message
from whatsapp_bot import meta
from whatsapp_bot.fake_meta import DEFAULT_BSUID, DEFAULT_PHONE
from whatsapp_bot.store import DONE
from whatsapp_bot.tests.conftest import APP_SECRET, VERIFY_TOKEN, publish_terms, run

OTHER_BSUID = "CD.2000000000000000002"

# La case des conditions fait partie de l'inscription WhatsApp : vraie exigence.
pytestmark = pytest.mark.conditions_reelles


def _accounts(main):
    from backend.app import ledger
    from backend.app.models import ChannelIdentity, NexisAccount

    with main.database.SessionLocal() as db:
        identities = db.execute(select(ChannelIdentity).where(ChannelIdentity.channel == ledger.WHATSAPP)).scalars().all()
        result = {}
        for identity in identities:
            account = db.get(NexisAccount, identity.account_id)
            result[identity.external_id] = account
        return result


def _acceptances(main):
    from backend.app.models import LegalAcceptance

    with main.database.SessionLocal() as db:
        return db.execute(select(LegalAcceptance)).scalars().all()


# --- Signature et validation de l'adresse -------------------------------------------


@pytest.mark.parametrize("case", ["absente", "fausse", "autre_corps", "autre_secret"])
def test_a_webhook_without_a_valid_signature_is_refused_before_anything(bench, case):
    async def scenario():
        async with bench:
            payload = bench.fake.text_message("Bonjour")
            body, headers = bench.fake.signed(payload)
            if case == "absente":
                headers = {"Content-Type": "application/json"}
            elif case == "fausse":
                headers = {**headers, "X-Hub-Signature-256": "sha256=" + "0" * 64}
            elif case == "autre_corps":
                body = body.replace(b"Bonjour", b"Bonsoir")
            else:
                from whatsapp_bot import signature

                headers = {**headers, "X-Hub-Signature-256": signature.sign("un-autre-secret", body)}
            response = await bench.post(payload, body=body, headers=headers)
            assert response.status_code == 401
            assert bench.fake.sent == []
            # Rien n'a touché Redis : aucun message noté, aucune étape.
            assert [key async for key in bench.redis.scan_iter(f"{bench.prefix}:*")] == []

    run(scenario)
    assert _accounts(bench.main) == {}


def test_meta_validates_the_webhook_address_with_the_verify_token(bench):
    async def scenario():
        import httpx

        async with bench:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=bench.app), base_url="http://w.test") as client:
                good = await client.get(
                    "/webhook", params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "1158201444"}
                )
                bad = await client.get(
                    "/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "faux", "hub.challenge": "1158201444"}
                )
            assert (good.status_code, good.text) == (200, "1158201444")
            assert bad.status_code == 403

    run(scenario)


# --- Inscription -----------------------------------------------------------------------


def test_a_new_client_signs_up_in_their_language_and_gets_the_menu(bench):
    async def scenario():
        async with bench:
            (welcome,) = await bench.say("Bonjour")
            assert welcome.kind == "button"
            assert [choice for choice, _ in welcome.choices] == ["lang:fr", "lang:ln", "lang:en"]
            assert _accounts(bench.main) == {}

            (ask_name,) = await bench.tap("lang:ln")
            assert ask_name.text == get_message("wa_ask_name", "ln")

            (terms,) = await bench.say("  Mado   Kabila ")
            assert terms.kind == "button", terms.text
            assert "https://nexis.example/conditions/cgu/2026-11-20?lang=ln" in terms.text
            assert [choice for choice, _ in terms.choices] == ["terms:accept", "terms:decline"]
            # Rien n'est créé avant « J'accepte ».
            assert _accounts(bench.main) == {}

            done = await bench.tap("terms:accept")
            assert [message.kind for message in done] == ["text", "list"]
            assert done[0].text == get_message("wa_registered", "ln", name="Mado Kabila")
            assert [choice for choice, _ in done[1].choices] == ["menu:new_request", "menu:language", "menu:provider", "menu:help"]
            # Réponses adressées au numéro donné par Meta.
            assert {message.to for message in bench.fake.sent} == {DEFAULT_PHONE}
            # Accusés de lecture envoyés pour chaque message traité.
            assert len(bench.fake.read) == 4

    run(scenario)
    account = _accounts(bench.main)[DEFAULT_BSUID]
    assert (account.language, account.phone_e164, "client" in account.roles) == ("ln", "+" + DEFAULT_PHONE, True)
    assert account.phone_verified_at is not None
    assert "provider" not in account.roles
    (acceptance,) = _acceptances(bench.main)
    assert (acceptance.account_id, acceptance.surface) == (account.id, "whatsapp")


def test_a_hidden_number_signs_up_by_bsuid_alone(bench):
    async def scenario():
        async with bench:
            await bench.register(phone=None)
            # Sans numéro, Meta est adressé par le BSUID.
            assert {(message.to, message.recipient) for message in bench.fake.sent} == {(None, DEFAULT_BSUID)}

    run(scenario)
    account = _accounts(bench.main)[DEFAULT_BSUID]
    assert (account.phone_e164, account.phone_verified_at) == (None, None)


def test_declining_the_terms_creates_nothing(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            await bench.say("Mado")
            (declined,) = await bench.tap("terms:decline")
            assert declined.text == get_message("wa_terms_declined", "fr")
            # Plus d'étape : le message suivant recommence par la langue.
            (welcome,) = await bench.say("Bonjour")
            assert welcome.choices[0][0] == "lang:fr"

    run(scenario)
    assert _accounts(bench.main) == {}


def test_terms_updated_between_the_screen_and_the_answer_are_shown_again(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            await bench.say("Mado")
            publish_terms(bench.main, "2026-12-01", at=_now(), documents=("cgu",))
            changed = await bench.tap("terms:accept")
            assert changed[0].text == get_message("wa_terms_changed", "fr")
            assert "/conditions/cgu/2026-12-01?lang=fr" in changed[1].text
            assert _accounts(bench.main) == {}
            await bench.tap("terms:accept")

    run(scenario)
    assert DEFAULT_BSUID in _accounts(bench.main)
    assert [row.version_id for row in _acceptances(bench.main)] != []


def test_a_number_already_proven_on_another_account_is_never_linked_by_itself(bench):
    async def scenario():
        async with bench:
            await bench.register(bsuid=OTHER_BSUID)
            sent = await bench.register(bsuid=DEFAULT_BSUID)
            assert [message.text for message in sent] == [get_message("wa_phone_owned", "fr")]

    run(scenario)
    assert set(_accounts(bench.main)) == {OTHER_BSUID}


def test_an_invalid_name_is_asked_again(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:en")
            (again,) = await bench.say("x" * 101)
            assert again.text == get_message("wa_name_invalid", "en")
            (terms,) = await bench.say("Mado")
            assert terms.kind == "button"

    run(scenario)


def test_without_published_terms_nobody_signs_up(backend_main):
    from whatsapp_bot.tests.conftest import Bench, _redis_or_skip

    _redis_or_skip()
    bench = Bench(backend_main)

    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            (closed,) = await bench.say("Mado")
            assert closed.text == get_message("terms_unavailable", "fr")

    run(scenario)
    assert _accounts(backend_main) == {}


def test_without_a_reading_page_the_terms_text_is_sent_in_the_chat(backend_main):
    from whatsapp_bot.conversation import Links
    from whatsapp_bot.tests.conftest import Bench, _redis_or_skip

    _redis_or_skip()
    publish_terms(backend_main)
    bench = Bench(backend_main, links=Links())

    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            header, text, question = await bench.say("Mado")
            assert "2026-11-20" in header.text
            assert text.text == "Texte cgu, version 2026-11-20."
            assert question.kind == "button" and "https://" not in question.text

    run(scenario)


# --- Client inscrit ---------------------------------------------------------------------


def test_a_client_who_wants_to_become_a_provider_is_sent_to_telegram(bench):
    async def scenario():
        async with bench:
            await bench.register()
            (refusal,) = await bench.tap("menu:provider")
            assert "https://t.me/NexisHubBot" in refusal.text and "https://nexis.example/app/" in refusal.text

    run(scenario)
    account = _accounts(bench.main)[DEFAULT_BSUID]
    assert "provider" not in account.roles


def test_a_client_changes_language(bench):
    async def scenario():
        async with bench:
            await bench.register()
            (buttons,) = await bench.tap("menu:language")
            assert [choice for choice, _ in buttons.choices] == ["lang:fr", "lang:ln", "lang:en"]
            updated, menu = await bench.tap("lang:en")
            assert updated.text == get_message("wa_language_updated", "en")
            assert menu.text == get_message("wa_menu", "en", name="Mado")

    run(scenario)
    assert _accounts(bench.main)[DEFAULT_BSUID].language == "en"


def test_any_text_from_a_client_shows_the_menu_and_help_answers(bench):
    async def scenario():
        async with bench:
            await bench.register()
            (menu,) = await bench.say("salut")
            assert menu.kind == "list"
            (help_text,) = await bench.tap("menu:help")
            assert help_text.text == get_message("wa_help", "fr")

    run(scenario)


@pytest.mark.parametrize("kind", ["image", "audio", "video", "document", "sticker"])
def test_photos_voice_notes_and_documents_are_refused(bench, kind):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            refused, ask_again = await bench._exchange(bench.fake.media_message(kind))
            assert refused.text == get_message("wa_media_refused", "fr")
            assert ask_again.text == get_message("wa_ask_name", "fr")

    run(scenario)


# --- Une seule fois, pannes ---------------------------------------------------------------


def test_a_replayed_webhook_is_handled_once(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            await bench.say("Mado")
            accept = bench.fake.choice_message("terms:accept")
            for _ in range(3):
                response = await bench.post(accept)
                assert response.status_code == 200
            assert len([m for m in bench.fake.sent if m.kind == "list"]) == 1

    run(scenario)
    assert len(_accounts(bench.main)) == 1
    assert len(_acceptances(bench.main)) == 1


def test_a_replay_after_redis_forgot_the_message_does_not_act_twice(bench):
    """Le registre Redis n'est qu'un filtre : le backend garde la garantie
    (même wamid, même réponse, rien de refait)."""

    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            await bench.say("Mado")
            state = await bench.store.conversation(DEFAULT_BSUID)
            accept = bench.fake.choice_message("terms:accept")
            assert (await bench.post(accept)).status_code == 200
            # Redis perd tout, et la conversation revient à « J'accepte ».
            await bench.redis.delete(*[key async for key in bench.redis.scan_iter(f"{bench.prefix}:*")])
            await bench.store.save_conversation(DEFAULT_BSUID, state)
            assert (await bench.post(accept)).status_code == 200

    run(scenario)
    assert len(_accounts(bench.main)) == 1
    assert len(_acceptances(bench.main)) == 1


def test_redis_emptied_in_the_middle_of_a_signup_starts_again_safely(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:ln")
            await bench.redis.delete(*[key async for key in bench.redis.scan_iter(f"{bench.prefix}:*")])
            (welcome,) = await bench.say("Mado")
            assert welcome.choices[0][0] == "lang:fr"
            # Un ancien bouton reste utilisable : la langue est reprise.
            (ask_name,) = await bench.tap("terms:accept")
            assert ask_name.kind == "button"  # étape oubliée : on repart de la langue
            (ask_name,) = await bench.tap("lang:ln")
            assert ask_name.text == get_message("wa_ask_name", "ln")

    run(scenario)
    assert _accounts(bench.main) == {}


def test_backend_down_answers_unavailable_and_replays_nothing_later(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            await bench.tap("lang:fr")
            await bench.say("Mado")
            bench.backend_down = True
            accept = bench.fake.choice_message("terms:accept")
            (unavailable,) = await bench._exchange(accept)
            assert unavailable.text == get_message("service_unavailable", "fr")
            # Le backend revient : le même webhook renvoyé par Meta ne fait rien.
            bench.backend_down = False
            assert (await bench.post(accept)).status_code == 200
            assert bench.fake.sent[-1] is unavailable
            assert _accounts(bench.main) == {}
            # La personne réessaie : l'étape n'a pas bougé.
            done = await bench.tap("terms:accept")
            assert done[0].text == get_message("wa_registered", "fr", name="Mado")

    run(scenario)
    assert len(_accounts(bench.main)) == 1


@pytest.mark.parametrize("failure", ["error", "server", "timeout"])
def test_a_reply_meta_did_not_take_is_retried_from_the_same_step(bench, failure):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")
            ask = bench.fake.choice_message("lang:fr")
            bench.fake.fail_next(failure)
            response = await bench.post(ask)
            assert response.status_code == 500
            assert (await bench.store.conversation(DEFAULT_BSUID)) == {"step": "language"}
            # Meta renvoie le webhook : la réponse part, une fois.
            (ask_name,) = await bench._exchange(ask)
            assert ask_name.text == get_message("wa_ask_name", "fr")
            assert (await bench.post(ask)).status_code == 200
            assert bench.fake.sent[-1] is ask_name

    run(scenario)


def test_two_messages_of_the_same_person_are_never_handled_together(bench):
    async def scenario():
        async with bench:
            await bench.store.lock(DEFAULT_BSUID, "une-autre-instance")
            hello = bench.fake.text_message("Bonjour")
            assert (await bench.post(hello)).status_code == 503
            assert bench.fake.sent == []
            await bench.store.unlock(DEFAULT_BSUID, "une-autre-instance")
            assert (await bench.post(hello)).status_code == 200
            assert len(bench.fake.sent) == 1

    run(scenario)


def test_a_message_being_handled_elsewhere_is_left_to_meta(bench):
    async def scenario():
        async with bench:
            hello = bench.fake.text_message("Bonjour")
            wamid = hello["entry"][0]["changes"][0]["value"]["messages"][0]["id"]
            assert await bench.store.claim(wamid) is not None
            assert (await bench.post(hello)).status_code == 503
            await bench.store.complete(wamid)
            assert (await bench.post(hello)).status_code == 200
            assert bench.fake.sent == []
            assert (await bench.redis.get(f"{bench.prefix}:msg:{wamid}")).decode() == DONE

    run(scenario)


def test_messages_for_another_number_or_without_identity_are_ignored(bench):
    async def scenario():
        async with bench:
            other = bench.fake.text_message("Bonjour")
            other["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "999"
            assert (await bench.post(other)).status_code == 200
            anonymous = bench.fake.text_message("Bonjour")
            value = anonymous["entry"][0]["changes"][0]["value"]
            del value["messages"][0]["from_user_id"]
            del value["contacts"][0]["user_id"]
            assert (await bench.post(anonymous)).status_code == 200
            statuses = bench.fake.text_message("x")
            statuses["entry"][0]["changes"][0]["value"] = {
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": bench.fake.phone_number_id},
                "statuses": [{"id": "wamid.X", "status": "delivered"}],
            }
            assert (await bench.post(statuses)).status_code == 200
            assert bench.fake.sent == []

    run(scenario)


# --- Journaux --------------------------------------------------------------------------


def test_logs_never_hold_numbers_texts_names_or_secrets(bench, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    # Les tests de migration chargent la configuration de journaux d'Alembic,
    # qui éteint les journaux déjà créés : on les rallume pour ce test.
    for name in ("whatsapp_bot.app", "whatsapp_bot.conversation", "whatsapp_bot.meta", "httpx"):
        monkeypatch.setattr(logging.getLogger(name), "disabled", False)

    async def scenario():
        async with bench:
            await bench.post(bench.fake.text_message("Mon secret 42"), signed=False)
            await bench.say("Bonjour tout le monde")
            await bench.tap("lang:fr")
            bench.fake.fail_next("error")
            await bench.post(bench.fake.text_message("Mado Kabila"))
            await bench.say("Mado Kabila")
            bench.backend_down = True
            await bench.tap("terms:accept")
            bench.backend_down = False
            await bench.tap("terms:accept")

    run(scenario)
    logs = "\n".join(record.getMessage() + (record.exc_text or "") for record in caplog.records)
    assert "Webhook refusé" in logs and "backend indisponible" in logs  # les journaux existent
    for forbidden in ("810000001", "Bonjour tout", "Mon secret", "Mado", "Kabila", APP_SECRET, "sha256=", "Bearer"):
        assert forbidden not in logs, forbidden


# --- Textes et limites de WhatsApp ---------------------------------------------------------


@pytest.mark.parametrize("lang", ["fr", "ln", "en"])
def test_every_screen_fits_whatsapp_limits_in_every_language(lang):
    from whatsapp_bot.conversation import Conversation, Links, _language_buttons, _welcome

    conversation = Conversation(backend=None, links=Links("https://t.me/NexisHubBot", "https://nexis.example/app/", "https://nexis.example"))
    documents = [{"document_key": "cgu", "version": "2026-11-20"}, {"document_key": "conditions_prestataires", "version": "2026-11-20"}]
    screens = [
        _welcome(),
        _language_buttons(get_message("wa_choose_language", lang)),
        conversation._menu(lang, "N" * 100),
        conversation._menu(lang, ""),
        *conversation._terms_screen("wa_terms_signup", documents, lang),
    ]
    for screen in screens:
        screen.payload()  # lève si une limite de WhatsApp est dépassée
    for key in ("wa_language_name", "wa_btn_accept", "wa_btn_decline", "wa_menu_button"):
        assert len(get_message(key, lang)) <= meta.MAX_BUTTON_TITLE, key
    meta.Text(conversation._provider_refusal(lang)).payload()


def test_meta_limits_are_enforced_before_sending():
    with pytest.raises(ValueError):
        meta.Buttons("Choix", (("a", "1"), ("b", "2"), ("c", "3"), ("d", "4"))).payload()
    with pytest.raises(ValueError):
        meta.Buttons("Choix", (("a", "Un libellé beaucoup trop long"),)).payload()
    with pytest.raises(ValueError):
        meta.Menu("Choix", "Menu", tuple((str(i), str(i), "") for i in range(11))).payload()


def _now():
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_an_identity_the_backend_refuses_gets_an_answer_and_is_not_retried_forever(bench):
    async def scenario():
        async with bench:
            # Format de BSUID que le backend refuse (`invalid_actor`).
            odd = bench.fake.text_message("Bonjour", bsuid="pas-un-bsuid")
            (answer,) = await bench._exchange(odd)
            assert answer.text == get_message("wa_error", "fr")
            assert (await bench.post(odd)).status_code == 200
            assert bench.fake.sent[-1] is answer

    run(scenario)
    assert _accounts(bench.main) == {}
