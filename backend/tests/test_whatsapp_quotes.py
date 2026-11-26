# ruff: noqa: F811  (fixtures pytest importées de test_whatsapp_missions)
"""Devis d'une mission WhatsApp (étape 6) : lire, accepter, refuser.

Mêmes règles que Telegram (un seul devis accepté, seul le client décide),
une décision par message WhatsApp (clé d'idempotence), et jamais un
identifiant Telegram dans ce que reçoit le client WhatsApp.
"""

import uuid

from backend.tests.test_whatsapp_channel import BSUID, OTHER_BSUID, as_telegram, as_whatsapp, register
from backend.tests.test_whatsapp_missions import (  # noqa: F401
    PROVIDER,
    api,
    backend,
    create_on_whatsapp,
    request_body,
    verified_provider,
)

OTHER_PROVIDER = 8


def _wa_write(bsuid=BSUID, key=None):
    return {**as_whatsapp(bsuid), "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}"}


def _mission_with_quotes(api, backend, *amounts):
    """Mission WhatsApp, puis un devis par prestataire Telegram prévenu."""
    providers = [PROVIDER, OTHER_PROVIDER][: len(amounts)]
    for telegram_id in providers:
        verified_provider(api, backend, telegram_id=telegram_id)
    register(api)
    mission_id = create_on_whatsapp(api, request_body()).json()["mission"]["mission_id"]
    quote_ids = []
    for telegram_id, amount in zip(providers, amounts):
        body = {"mission_id": mission_id, "amount": amount, "currency": "USD", "delay_hours": 4, "message": "Je passe ce soir"}
        response = api.post("/api/bot/quotes", json=body, headers=as_telegram(telegram_id))
        assert response.status_code == 200, response.json()
        quote_ids.append(response.json()["quote"]["id"])
    return mission_id, quote_ids


def _statuses(api, mission_id):
    body = api.get(f"/api/bot/missions/{mission_id}/quotes", headers=as_whatsapp()).json()
    return body["mission"]["status"], [quote["status"] for quote in body["quotes"]]


def test_the_client_reads_the_quotes_of_their_mission_without_telegram_ids(api, backend):
    mission_id, quote_ids = _mission_with_quotes(api, backend, 40, 55)
    body = api.get(f"/api/bot/missions/{mission_id}/quotes", headers=as_whatsapp()).json()
    assert [quote["id"] for quote in body["quotes"]] == quote_ids
    first = body["quotes"][0]
    assert (first["amount"], first["currency"], first["delay_hours"], first["provider_name"]) == (40, "USD", 4, f"Prestataire {PROVIDER}")
    assert first["provider_trust"]["is_verified"] is True
    for forbidden in ("telegram_id", "provider_telegram_id"):
        assert forbidden not in repr(body)
    assert str(PROVIDER) not in repr({key: value for key, value in first.items() if key != "provider_name"})
    one = api.get(f"/api/bot/quotes/{quote_ids[0]}", headers=as_whatsapp()).json()
    assert one["quote"]["id"] == quote_ids[0] and "provider_telegram_id" not in repr(one)


def test_nobody_else_reads_the_quotes(api, backend):
    mission_id, quote_ids = _mission_with_quotes(api, backend, 40)
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    other = api.get(f"/api/bot/missions/{mission_id}/quotes", headers=as_whatsapp(OTHER_BSUID))
    assert (other.status_code, other.json()["detail"]["code"]) == (404, "mission_not_found")
    unknown = api.get(f"/api/bot/quotes/{quote_ids[0]}", headers=as_whatsapp(OTHER_BSUID))
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (404, "quote_not_found")
    # Le prestataire lit son propre devis, pas la liste du client.
    assert api.get(f"/api/bot/quotes/{quote_ids[0]}", headers=as_telegram(PROVIDER)).status_code == 200
    assert api.get(f"/api/bot/missions/{mission_id}/quotes", headers=as_telegram(PROVIDER)).status_code == 404


def test_accepting_one_quote_rejects_the_others_like_on_telegram(api, backend):
    mission_id, (first, second) = _mission_with_quotes(api, backend, 40, 55)
    response = api.post(f"/api/bot/quotes/{second}/accept", headers=_wa_write())
    assert response.status_code == 200, response.json()
    assert response.json()["quote"]["status"] == "accepted"
    assert "provider_telegram_id" not in repr(response.json())
    assert _statuses(api, mission_id) == ("confirmed", ["rejected", "accepted"])
    # Le prestataire choisi est prévenu (notification, sur Telegram).
    from backend.app.models import Notification

    with backend.database.SessionLocal() as db:
        keys = {row.event_key for row in db.query(Notification)}
    assert f"quote_accepted:{second}" in keys


def test_the_same_accept_message_replayed_answers_the_same(api, backend):
    mission_id, (quote_id,) = _mission_with_quotes(api, backend, 40)
    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa_write(key=key))
    replay = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa_write(key=key))
    assert first.status_code == replay.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert replay.json() == first.json()
    # Un second appui (autre message) : même devis accepté, rien de plus.
    again = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa_write())
    assert again.status_code == 200 and again.json()["quote"]["status"] == "accepted"
    from backend.app.models import Notification

    with backend.database.SessionLocal() as db:
        assert db.query(Notification).filter(Notification.event_key == f"quote_accepted:{quote_id}").count() == 1


def test_an_accept_needs_its_message_key(api, backend):
    mission_id, (quote_id,) = _mission_with_quotes(api, backend, 40)
    response = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=as_whatsapp())
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "idempotency_key_required")
    assert _statuses(api, mission_id) == ("quoted", ["pending"])


def test_only_the_client_of_the_mission_decides(api, backend):
    mission_id, (quote_id,) = _mission_with_quotes(api, backend, 40)
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    response = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa_write(OTHER_BSUID))
    assert (response.status_code, response.json()["detail"]["code"]) == (403, "not_mission_client")
    unknown = api.post(f"/api/bot/quotes/{quote_id}/reject", headers=_wa_write("CD.777000111"))
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (403, "not_mission_client")
    assert _statuses(api, mission_id) == ("quoted", ["pending"])


def test_a_rejected_quote_can_no_longer_be_accepted(api, backend):
    mission_id, (quote_id,) = _mission_with_quotes(api, backend, 40)
    assert api.post(f"/api/bot/quotes/{quote_id}/reject", headers=_wa_write()).json()["quote"]["status"] == "rejected"
    late = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa_write())
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "quote_not_open")


def test_an_accepted_quote_can_no_longer_be_rejected(api, backend):
    mission_id, (quote_id,) = _mission_with_quotes(api, backend, 40)
    api.post(f"/api/bot/quotes/{quote_id}/accept", headers=_wa_write())
    late = api.post(f"/api/bot/quotes/{quote_id}/reject", headers=_wa_write())
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "quote_not_open")
    assert _statuses(api, mission_id) == ("confirmed", ["accepted"])


def test_an_unknown_quote_is_a_stable_refusal(api, backend):
    register(api)
    response = api.post("/api/bot/quotes/999/accept", headers=_wa_write())
    assert (response.status_code, response.json()["detail"]["code"]) == (404, "quote_not_found")


def test_telegram_still_decides_without_a_key_and_keeps_its_ids(api, backend):
    verified_provider(api, backend)
    assert api.put("/api/me/client-profile", json={"first_name": "Mado"}, headers=as_telegram(42)).status_code == 200
    mission_id = api.post("/api/bot/missions", json=request_body(), headers=as_telegram(42)).json()["mission"]["mission_id"]
    body = {"mission_id": mission_id, "amount": 40, "currency": "USD", "delay_hours": 4, "message": ""}
    quote_id = api.post("/api/bot/quotes", json=body, headers=as_telegram(PROVIDER)).json()["quote"]["id"]
    accepted = api.post(f"/api/bot/quotes/{quote_id}/accept", headers=as_telegram(42))
    assert accepted.status_code == 200
    assert accepted.json()["quote"]["provider_telegram_id"] == PROVIDER
    assert accepted.json()["mission"]["telegram_id"] == 42
