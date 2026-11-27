# ruff: noqa: F811  (fixtures pytest importées de test_whatsapp_missions)
"""Suivi d'une mission par un client WhatsApp (étape 7) : arrivée, fin,
litige, avis, solde.

Mêmes règles et mêmes montants que Telegram, au centime ; une décision par
message (clé d'idempotence), jamais deux libérations ; seul le client de la
mission agit ou lit ; jamais un identifiant Telegram dans ce que reçoit le
client WhatsApp.
"""

import uuid

import pytest

from backend.tests.test_whatsapp_channel import BSUID, OTHER_BSUID, as_telegram, as_whatsapp, register
from backend.tests.test_whatsapp_missions import PROVIDER, api, backend  # noqa: F401
from backend.tests.test_whatsapp_paiement import (
    TELEGRAM_CLIENT,
    _accepted_mission_on_telegram,
    _accepted_mission_on_whatsapp,
    _credit,
    _no_telegram_ids,
    _pay_wallet,
    _wallet,
)


def _wa(bsuid=BSUID, key=None):
    return {**as_whatsapp(bsuid), "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}"}


def _paid_on_whatsapp(api, backend, amount="37.35"):
    mission_id, quote_id = _accepted_mission_on_whatsapp(api, backend, amount=amount)
    _credit(api, backend, as_whatsapp(), 100)
    assert _pay_wallet(api, mission_id, quote_id).status_code == 200
    return mission_id


def _paid_on_telegram(api, backend, amount="37.35"):
    mission_id, quote_id = _accepted_mission_on_telegram(api, amount=amount)
    _credit(api, backend, as_telegram(TELEGRAM_CLIENT), 100)
    body = {"method": "wallet", "quote_id": quote_id}
    assert api.post(f"/api/bot/missions/{mission_id}/fund", json=body, headers=as_telegram(TELEGRAM_CLIENT)).status_code == 200
    return mission_id


def _arrived(api, mission_id):
    assert api.post(f"/api/bot/missions/{mission_id}/presence/arrived", headers=as_telegram(PROVIDER)).status_code == 200


def _finished(api, mission_id, client_headers):
    _arrived(api, mission_id)
    assert api.post(f"/api/bot/missions/{mission_id}/presence/confirm", headers=client_headers).status_code == 200
    assert api.post(f"/api/bot/missions/{mission_id}/finish", headers=as_telegram(PROVIDER)).status_code == 200


def _settlements(backend, mission_id):
    from backend.app.ledger import SETTLEMENT, MoneyOperation

    with backend.database.SessionLocal() as db:
        return db.query(MoneyOperation).filter_by(mission_id=mission_id, phase=SETTLEMENT).count()


def _notifications(backend, event_key):
    from backend.app.models import Notification

    with backend.database.SessionLocal() as db:
        return db.query(Notification).filter(Notification.event_key == event_key).count()


# --- Arrivée ------------------------------------------------------------------------


def test_the_client_reads_the_presence_code_and_confirms_the_arrival_once(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    shown = api.get(f"/api/bot/missions/{mission_id}/presence", headers=as_whatsapp()).json()
    assert len(shown["presence"]["code"]) == 4
    _arrived(api, mission_id)
    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post(f"/api/bot/missions/{mission_id}/presence/confirm", headers=_wa(key=key))
    replay = api.post(f"/api/bot/missions/{mission_id}/presence/confirm", headers=_wa(key=key))
    again = api.post(f"/api/bot/missions/{mission_id}/presence/confirm", headers=_wa())
    assert first.status_code == replay.status_code == again.status_code == 200, first.json()
    assert replay.headers.get("Idempotent-Replayed") == "true" and replay.json() == first.json()
    assert first.json()["mission"]["status"] == "in_progress" and first.json()["presence"]["confirmed"] is True
    assert first.json()["presence"]["code"] is None  # plus utile une fois confirmé
    _no_telegram_ids(first.json())
    assert _notifications(backend, f"presence_confirmed:{mission_id}:provider") <= 1


def test_not_yet_and_nobody_else_answers_for_the_client(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    _arrived(api, mission_id)
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    for path in ("presence/confirm", "presence/not-yet", "presence/wrong-person", "confirm"):
        refused = api.post(f"/api/bot/missions/{mission_id}/{path}", headers=_wa(OTHER_BSUID))
        assert (refused.status_code, refused.json()["detail"]["code"]) == (403, "not_mission_client")
        assert "mission" not in refused.json()["detail"]
    hidden = api.get(f"/api/bot/missions/{mission_id}/presence", headers=as_whatsapp(OTHER_BSUID))
    assert (hidden.status_code, hidden.json()["detail"]["code"]) == (404, "mission_not_found")
    not_yet = api.post(f"/api/bot/missions/{mission_id}/presence/not-yet", headers=_wa())
    assert not_yet.status_code == 200 and not_yet.json()["mission"]["status"] == "confirmed"


def test_not_him_freezes_the_money_like_on_telegram(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    _arrived(api, mission_id)
    reported = api.post(f"/api/bot/missions/{mission_id}/presence/wrong-person", headers=_wa())
    assert reported.status_code == 200 and reported.json()["mission"]["status"] == "disputed"
    assert reported.json()["presence"]["wrong_person_reported"] is True
    late = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa())
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "mission_disputed")
    assert _settlements(backend, mission_id) == 0


# --- Fin de mission -----------------------------------------------------------------


def test_confirming_the_end_pays_the_provider_like_on_telegram_to_the_cent(api, backend):
    whatsapp_mission = _paid_on_whatsapp(api, backend)
    telegram_mission = _paid_on_telegram(api, backend)
    _finished(api, whatsapp_mission, _wa())
    _finished(api, telegram_mission, as_telegram(TELEGRAM_CLIENT))
    provider_before = _wallet(api, as_telegram(PROVIDER))

    on_whatsapp = api.post(f"/api/bot/missions/{whatsapp_mission}/confirm", headers=_wa())
    on_telegram = api.post(f"/api/bot/missions/{telegram_mission}/confirm", headers=as_telegram(TELEGRAM_CLIENT))
    assert on_whatsapp.status_code == on_telegram.status_code == 200, on_whatsapp.json()
    settled = [response.json()["money"]["settlement"] for response in (on_whatsapp, on_telegram)]
    for settlement in settled:
        settlement.pop("reference", None)
    assert settled[0] == settled[1]
    assert (settled[0]["provider_amount"], settled[0]["platform_amount"]) == ("31.75", "5.60")
    assert on_whatsapp.json()["mission"]["payment_status"] == "released"
    assert _wallet(api, as_telegram(PROVIDER)) == pytest.approx(provider_before + 2 * 31.75)
    _no_telegram_ids(on_whatsapp.json())


def test_a_double_tap_or_a_replay_on_confirm_pays_once(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    _finished(api, mission_id, _wa())
    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa(key=key))
    replay = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa(key=key))
    second_tap = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa())
    assert first.status_code == replay.status_code == second_tap.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true" and replay.json() == first.json()
    assert _settlements(backend, mission_id) == 1
    assert _wallet(api, as_telegram(PROVIDER)) == pytest.approx(31.75)
    assert _notifications(backend, f"mission_released:{mission_id}") <= 1


def test_confirm_needs_its_message_key_and_a_finished_mission(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    no_key = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=as_whatsapp())
    assert (no_key.status_code, no_key.json()["detail"]["code"]) == (400, "idempotency_key_required")
    early = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa())
    assert (early.status_code, early.json()["detail"]["code"]) == (409, "invalid_state")
    _no_telegram_ids(early.json())
    assert _settlements(backend, mission_id) == 0


# --- Litige -------------------------------------------------------------------------


def test_reporting_a_problem_freezes_the_money_once(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    _finished(api, mission_id, _wa())
    key = f"wamid.{uuid.uuid4().hex}"
    body = {"reason": "Travail mal fait : la cuisine n'est pas nettoyée"}
    first = api.post(f"/api/bot/missions/{mission_id}/dispute", json=body, headers=_wa(key=key))
    replay = api.post(f"/api/bot/missions/{mission_id}/dispute", json=body, headers=_wa(key=key))
    other = api.post(f"/api/bot/missions/{mission_id}/dispute", json={"reason": "Autre motif"}, headers=_wa())
    assert first.status_code == replay.status_code == other.status_code == 200, first.json()
    assert first.json()["mission"]["status"] == "disputed" and replay.json() == first.json()
    assert _notifications(backend, f"dispute_opened:{mission_id}") <= 1
    from backend.app.models import BotMission

    with backend.database.SessionLocal() as db:
        assert db.get(BotMission, mission_id).dispute_reason == body["reason"]
    late = api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa())
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "mission_disputed")
    reused = api.post(f"/api/bot/missions/{mission_id}/dispute", json={"reason": "Changé"}, headers=_wa(key=key))
    assert (reused.status_code, reused.json()["detail"]["code"]) == (409, "idempotency_key_reused")


def test_an_empty_reason_is_refused_and_nothing_is_kept(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    key = f"wamid.{uuid.uuid4().hex}"
    refused = api.post(f"/api/bot/missions/{mission_id}/dispute", json={"reason": "  "}, headers=_wa(key=key))
    assert (refused.status_code, refused.json()["detail"]["code"]) == (400, "invalid_reason")
    assert api.get(f"/api/bot/missions/{mission_id}/presence", headers=as_whatsapp()).status_code == 200


# --- Avis ---------------------------------------------------------------------------


def test_a_whatsapp_client_rates_the_provider_once(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    _finished(api, mission_id, _wa())
    assert api.post(f"/api/bot/missions/{mission_id}/confirm", headers=_wa()).status_code == 200
    key = f"wamid.{uuid.uuid4().hex}"
    body = {"mission_id": mission_id, "rating": 4, "comment": "Bon travail"}
    first = api.post("/api/bot/reviews", json=body, headers=_wa(key=key))
    replay = api.post("/api/bot/reviews", json=body, headers=_wa(key=key))
    assert first.status_code == replay.status_code == 200, first.json()
    assert replay.json() == first.json()
    review = first.json()["review"]
    assert (review["rating"], review["comment"]) == (4, "Bon travail")
    _no_telegram_ids(first.json())
    second = api.post("/api/bot/reviews", json={**body, "rating": 1}, headers=_wa())
    assert (second.status_code, second.json()["detail"]["code"]) == (400, "already_reviewed")
    from backend.app.models import BotReview, ProviderProfile

    with backend.database.SessionLocal() as db:
        (row,) = db.query(BotReview).all()
        assert row.client_telegram_id is None and row.client_account_id is not None
        provider = db.query(ProviderProfile).filter_by(account_id=row.provider_account_id).one()
        assert (provider.average_rating, provider.total_reviews) == (4.0, 1)


def test_only_the_client_rates_and_a_rating_is_between_1_and_5(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    other = api.post("/api/bot/reviews", json={"mission_id": mission_id, "rating": 5}, headers=_wa(OTHER_BSUID))
    assert (other.status_code, other.json()["detail"]["code"]) == (400, "not_mission_client")
    wrong = api.post("/api/bot/reviews", json={"mission_id": mission_id, "rating": 6}, headers=_wa())
    assert (wrong.status_code, wrong.json()["detail"]["code"]) == (400, "invalid_rating")


# --- Solde --------------------------------------------------------------------------


def test_the_client_reads_their_own_wallet_history_only(api, backend):
    mission_id = _paid_on_whatsapp(api, backend)
    entries = api.get("/api/me/wallet/history", headers=as_whatsapp()).json()["entries"]
    assert [(entry["kind"], entry["amount"], entry["mission_id"]) for entry in entries] == [
        ("fund_wallet", "-37.35", mission_id),
        ("opening_balance", "100.00", None),
    ]
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    assert api.get("/api/me/wallet/history", headers=as_whatsapp(OTHER_BSUID)).json()["entries"] == []
