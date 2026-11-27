"""Service WhatsApp, étape 8 : les notifications arrivent sur WhatsApp.

Banc d'essai : whatsapp_bot/tests/conftest.py (vrai backend, faux Meta, vrai
Redis). L'expéditeur de notifications du backend (backend/app/notify_whatsapp.py)
écrit au même faux Meta que le service ; les statuts et événements de Meta
passent par le webhook du service, comme en vrai.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from whatsapp_bot import conversation, devis, litige, paiement, suivi
from whatsapp_bot.fake_meta import DEFAULT_BSUID, DEFAULT_PHONE
from whatsapp_bot.tests.conftest import ACCESS_TOKEN, GRAPH_URL, PHONE_NUMBER_ID, provider_quote, run, verified_provider
from whatsapp_bot.tests.test_whatsapp_demande import _choices
from whatsapp_bot.tests.test_whatsapp_devis import _mission_on_whatsapp

pytestmark = pytest.mark.conditions_reelles


def _sender(bench, monkeypatch):
    """Le backend envoie ses notifications WhatsApp au faux Meta du banc."""
    from backend.app import notifications, notify_whatsapp

    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", ACCESS_TOKEN)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    monkeypatch.setenv("WHATSAPP_GRAPH_URL", GRAPH_URL)
    monkeypatch.setenv("WHATSAPP_CALLBACK_KEY", "test-callback-key-not-a-secret-0000000001")
    api = TestClient(bench.fake.app())
    monkeypatch.setattr(notify_whatsapp, "_http_post", lambda url, json, headers, timeout: api.post(url, json=json, headers=headers))
    monkeypatch.setattr(notifications, "_TRANSPORTS", {"whatsapp": notify_whatsapp.WhatsAppTransport()})


def _rows(main, prefix):
    from backend.app.models import Notification

    with main.database.SessionLocal() as db:
        return db.query(Notification).filter(Notification.event_key.like(f"{prefix}%")).order_by(Notification.id).all()


def _last_inbound(main):
    from backend.app.models import ChannelIdentity

    with main.database.SessionLocal() as db:
        return db.query(ChannelIdentity.last_inbound_at).filter_by(channel="whatsapp", external_id=DEFAULT_BSUID).scalar()


def _went_quiet(bench, hours, *, backend=True, meta=True):
    """Le client n'a plus écrit depuis `hours` heures."""
    from backend.app.models import ChannelIdentity

    if backend:
        with bench.main.database.SessionLocal() as db:
            identity = db.query(ChannelIdentity).filter_by(channel="whatsapp", external_id=DEFAULT_BSUID).one()
            identity.last_inbound_at = datetime.utcnow() - timedelta(hours=hours)
            db.commit()
    if meta:
        for address in (DEFAULT_BSUID, DEFAULT_PHONE):
            bench.fake.inbound[address] = bench.fake.clock() - hours * 3600


def _admin(main):
    from backend.tests import profils_de_test

    with main.database.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        db.commit()


def test_each_message_received_opens_the_24_hour_window(bench):
    async def scenario():
        async with bench:
            await bench.say("Bonjour")  # pas encore inscrit : rien à noter
            assert _last_inbound(bench.main) is None
            await bench.register()
            first = _last_inbound(bench.main)
            assert first is not None and datetime.utcnow() - first < timedelta(minutes=1)
            # Un message rejoué, plus ancien, ne recule jamais l'heure.
            old = bench.fake.text_message("menu")
            old["entry"][0]["changes"][0]["value"]["messages"][0]["timestamp"] = "1700000000"
            assert (await bench.post(old)).status_code == 200
            assert _last_inbound(bench.main) == first

    run(scenario)


def test_inside_the_window_the_quote_arrives_with_its_buttons_and_works(bench, monkeypatch):
    verified_provider(bench.main, telegram_id=7)
    _sender(bench, monkeypatch)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            before = len(bench.fake.sent)
            quote_id = provider_quote(bench.main, mission_id, telegram_id=7, amount=40)
            (card,) = bench.fake.sent[before:]
            assert card.kind == "button" and card.callback
            assert _choices([card]) == [f"quote_accept_{quote_id}", f"quote_reject_{quote_id}"]
            assert "*NXH-0001*" in card.text and "40.00 USD" in card.text and "<b>" not in card.text
            accepted = await bench.tap(f"quote_accept_{quote_id}")
            assert accepted[0].text.startswith("✅")
            (row,) = _rows(bench.main, "quote_received:")
            assert row.status == "sent" and row.channel == "whatsapp"

    run(scenario)


def test_outside_the_window_the_template_opens_the_request(bench, monkeypatch):
    verified_provider(bench.main, telegram_id=7)
    _sender(bench, monkeypatch)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            _went_quiet(bench, 30)
            before = len(bench.fake.sent)
            quote_id = provider_quote(bench.main, mission_id, telegram_id=7, amount=40)
            (template,) = bench.fake.sent[before:]
            assert template.template["name"] == "nexis_suivi"
            payload = template.template["components"][1]["parameters"][0]["payload"]
            assert payload == f"mis:{mission_id}"
            # Le client appuie sur le bouton du modèle : la demande et le devis
            # s'affichent, dans la fenêtre rouverte.
            before = len(bench.fake.sent)
            assert (await bench.post(bench.fake.template_reply(payload))).status_code == 200
            shown = bench.fake.sent[before:]
            assert "NXH-0001" in shown[0].text
            assert [f"quote_accept_{quote_id}", f"quote_reject_{quote_id}"] in [_choices([m]) for m in shown if m.kind == "button"]
            assert datetime.utcnow() - _last_inbound(bench.main) < timedelta(minutes=1)
            # Statut « remis » relayé : rien ne change, rien n'est renvoyé.
            assert (await bench.post(bench.fake.status_webhook())).status_code == 200
            (row,) = _rows(bench.main, "quote_received:")
            assert row.status == "sent" and row.provider_message_id == template.wamid

    run(scenario)


def test_a_free_message_refused_by_meta_leaves_again_as_a_template(bench, monkeypatch):
    """Le backend croit la fenêtre ouverte, Meta non : Meta accepte puis
    refuse par un statut (131047). Le service relaie, le backend renvoie le
    modèle tout de suite, une seule fois."""
    verified_provider(bench.main, telegram_id=7)
    _sender(bench, monkeypatch)

    async def scenario():
        async with bench:
            mission_id = await _mission_on_whatsapp(bench)
            _went_quiet(bench, 30, backend=False)
            before = len(bench.fake.sent)
            provider_quote(bench.main, mission_id, telegram_id=7, amount=40)
            (free,) = bench.fake.sent[before:]
            assert free.kind == "button"
            refusal = bench.fake.status_webhook()
            bench.backend_down = True
            assert (await bench.post(refusal)).status_code == 500  # Meta renverra
            bench.backend_down = False
            assert (await bench.post(refusal)).status_code == 200
            (template,) = bench.fake.sent[before + 1 :]
            assert template.template is not None
            # Webhook de Meta reçu deux fois : rien de plus.
            assert (await bench.post(refusal)).status_code == 200
            assert len(bench.fake.sent) == before + 2
            assert (await bench.post(bench.fake.status_webhook())).status_code == 200
            (row,) = _rows(bench.main, "quote_received:")
            assert row.status == "sent" and row.template_required and row.provider_message_id == template.wamid

    run(scenario)


def test_a_template_paused_by_meta_reaches_the_team_and_notifications_wait(bench, monkeypatch):
    verified_provider(bench.main, telegram_id=7)
    _admin(bench.main)
    _sender(bench, monkeypatch)

    async def scenario():
        async with bench:
            event = bench.fake.template_event("nexis_suivi", "fr", "PAUSED", reason="LOW_QUALITY")
            assert (await bench.post(event)).status_code == 200
            assert (await bench.post(event)).status_code == 200
            (alert,) = _rows(bench.main, "whatsapp_meta:")
            assert "mis en pause" in alert.params["text"]["$html"]

            bench.fake.templates[("nexis_suivi", "fr")] = "PAUSED"
            mission_id = await _mission_on_whatsapp(bench)
            _went_quiet(bench, 30)
            before = len(bench.fake.sent)
            provider_quote(bench.main, mission_id, telegram_id=7, amount=40)
            assert bench.fake.sent[before:] == []
            (row,) = _rows(bench.main, "quote_received:")
            assert row.status == "pending" and row.attempts == 0

    run(scenario)


def test_statuses_of_ordinary_replies_are_not_relayed(bench):
    async def scenario():
        async with bench:
            replies = await bench.register()
            status = bench.fake.status(replies[0], "delivered")
            assert (await bench.post(bench.fake.status_webhook([status]))).status_code == 200

    run(scenario)


@pytest.mark.parametrize("action", __import__("backend.app.notify_whatsapp", fromlist=["x"]).WHATSAPP_ACTIONS)
def test_every_button_sent_in_a_notification_is_understood_by_the_service(action):
    """Les boutons que l'expéditeur montre sur WhatsApp
    (notify_whatsapp.WHATSAPP_ACTIONS) sont traités par la conversation."""
    if action == "menu:":
        handled = [conversation.MENU_MISSIONS, conversation.MENU_WALLET, conversation.MENU_NEW_REQUEST]
        assert all(choice.startswith(action) for choice in handled)
        return
    choice = f"{action}7"
    assert any(
        (devis.handles(choice, {}), suivi.handles(choice, {}), litige.handles(choice, {}), paiement.handles(choice))
    ), action
