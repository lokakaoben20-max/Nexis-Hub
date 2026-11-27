# ruff: noqa: F811  (fixtures pytest importées de test_whatsapp_missions)
"""Litige d'un client WhatsApp (étape 7b) : contester la décision de
NexisHub, proposer un accord amiable.

Mêmes règles et mêmes montants que Telegram, au centime ; une décision par
message (clé d'idempotence) ; seul le client de la mission agit ; jamais un
identifiant Telegram dans ce que reçoit le client WhatsApp.
"""

import uuid

from backend.tests.test_whatsapp_channel import OTHER_BSUID, as_telegram, as_whatsapp, register
from backend.tests.test_whatsapp_missions import PROVIDER, api, backend  # noqa: F401
from backend.tests.test_whatsapp_paiement import TELEGRAM_CLIENT, _no_telegram_ids, _wallet
from backend.tests.test_whatsapp_suivi import _finished, _notifications, _paid_on_telegram, _paid_on_whatsapp, _settlements, _wa

ADMIN_TELEGRAM = 900


def _disputed(api, backend, headers, paid):
    mission_id = paid(api, backend)
    whatsapp = headers.get("X-Actor-Channel") == "whatsapp"
    _finished(api, mission_id, _wa() if whatsapp else headers)
    reported = api.post(f"/api/bot/missions/{mission_id}/dispute", json={"reason": "Travail pas terminé"}, headers=_wa() if whatsapp else headers)
    assert reported.status_code == 200, reported.json()
    return mission_id


def _decide(backend, mission_id, decision="split", percentage=40):
    from backend.app import ledger

    with backend.database.SessionLocal() as db:
        admin = ledger.account_id_for(db, ledger.TELEGRAM, ADMIN_TELEGRAM, create=True)
        db.commit()
        ledger.decide_dispute(
            db, mission_id, decision=decision, admin_account_id=admin, admin_telegram_id=ADMIN_TELEGRAM, provider_percentage=percentage
        )
        return ledger.dispute_decisions(db, mission_id)[0].id


# --- Contester la décision ------------------------------------------------------------


def test_the_whatsapp_client_contests_the_decision_once(api, backend):
    mission_id = _disputed(api, backend, as_whatsapp(), _paid_on_whatsapp)
    decision_id = _decide(backend, mission_id)
    shown = api.get(f"/api/bot/missions/{mission_id}/quotes", headers=as_whatsapp()).json()
    assert [row["state"] for row in shown["money"]["dispute_decisions"]] == ["pending"]
    _no_telegram_ids(shown)

    no_key = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "Pas d'accord"}, headers=as_whatsapp())
    assert (no_key.status_code, no_key.json()["detail"]["code"]) == (400, "idempotency_key_required")
    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "Pas d'accord"}, headers=_wa(key=key))
    replay = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "Pas d'accord"}, headers=_wa(key=key))
    other_tap = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "Pas d'accord"}, headers=_wa())
    assert first.status_code == replay.status_code == other_tap.status_code == 200, first.json()
    assert replay.headers["Idempotent-Replayed"] == "true" and replay.json() == first.json()
    decision = first.json()["money"]["dispute_decisions"][0]
    assert (decision["state"], decision["contested_by"]) == ("contested", "client")
    _no_telegram_ids(first.json())
    assert _notifications(backend, f"dispute_contested:{decision_id}") == 1
    assert _settlements(backend, mission_id) == 0


def test_contesting_needs_a_decision_and_the_client(api, backend):
    mission_id = _disputed(api, backend, as_whatsapp(), _paid_on_whatsapp)
    early = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "Non"}, headers=_wa())
    assert (early.status_code, early.json()["detail"]["code"]) == (409, "no_decision")
    _decide(backend, mission_id)
    register(api, OTHER_BSUID)
    stranger = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "Non"}, headers=_wa(OTHER_BSUID))
    assert stranger.status_code == 403
    assert stranger.json()["detail"] == {"code": "not_mission_party"}  # rien sur la mission
    empty = api.post(f"/api/bot/missions/{mission_id}/dispute/contest", json={"reason": "  "}, headers=_wa())
    assert (empty.status_code, empty.json()["detail"]["code"]) == (400, "invalid_reason")


# --- Accord amiable ---------------------------------------------------------------------


def test_an_offer_from_whatsapp_has_the_same_amounts_as_on_telegram_and_is_sent_once(api, backend):
    whatsapp_mission = _disputed(api, backend, as_whatsapp(), _paid_on_whatsapp)
    telegram_mission = _disputed(api, backend, as_telegram(TELEGRAM_CLIENT), _paid_on_telegram)
    body = {"kind": "split", "provider_percentage": 50}
    key = f"wamid.{uuid.uuid4().hex}"
    first = api.post(f"/api/bot/missions/{whatsapp_mission}/dispute/offers", json=body, headers=_wa(key=key))
    replay = api.post(f"/api/bot/missions/{whatsapp_mission}/dispute/offers", json=body, headers=_wa(key=key))
    again = api.post(f"/api/bot/missions/{whatsapp_mission}/dispute/offers", json=body, headers=_wa())
    assert first.status_code == replay.status_code == again.status_code == 200, first.json()
    offers = again.json()["money"]["dispute_offers"]
    assert len(offers) == 1 and offers[0]["state"] == "pending"
    _no_telegram_ids(first.json())
    telegram = api.post(f"/api/bot/missions/{telegram_mission}/dispute/offers", json=body, headers=as_telegram(TELEGRAM_CLIENT))
    assert telegram.status_code == 200
    amounts = ("provider_amount", "client_amount", "platform_amount")
    assert {k: offers[0][k] for k in amounts} == {k: telegram.json()["money"]["dispute_offers"][0][k] for k in amounts}
    assert _notifications(backend, f"offer_proposed:{offers[0]['id']}") == 1

    other = api.post(f"/api/bot/missions/{whatsapp_mission}/dispute/offers", json={"kind": "refund"}, headers=_wa())
    assert (other.status_code, other.json()["detail"]["code"]) == (409, "offer_pending")
    reused = api.post(f"/api/bot/missions/{whatsapp_mission}/dispute/offers", json={"kind": "refund"}, headers=_wa(key=key))
    assert (reused.status_code, reused.json()["detail"]["code"]) == (409, "idempotency_key_reused")

    before = _wallet(api, as_whatsapp())
    accepted = api.post(
        f"/api/bot/missions/{whatsapp_mission}/dispute/offers/{offers[0]['id']}/accept", headers=as_telegram(PROVIDER)
    )
    assert accepted.status_code == 200, accepted.json()
    assert _settlements(backend, whatsapp_mission) == 1
    assert round(_wallet(api, as_whatsapp()) - before, 2) == float(offers[0]["client_amount"])


def test_offers_are_refused_after_a_decision_and_for_anyone_else(api, backend):
    mission_id = _disputed(api, backend, as_whatsapp(), _paid_on_whatsapp)
    register(api, OTHER_BSUID)
    stranger = api.post(f"/api/bot/missions/{mission_id}/dispute/offers", json={"kind": "redo"}, headers=_wa(OTHER_BSUID))
    assert stranger.status_code == 403 and stranger.json()["detail"] == {"code": "not_mission_client"}
    invalid = api.post(f"/api/bot/missions/{mission_id}/dispute/offers", json={"kind": "gift"}, headers=_wa())
    assert (invalid.status_code, invalid.json()["detail"]["code"]) == (400, "invalid_offer")
    _decide(backend, mission_id)
    late = api.post(f"/api/bot/missions/{mission_id}/dispute/offers", json={"kind": "redo"}, headers=_wa())
    assert (late.status_code, late.json()["detail"]["code"]) == (409, "already_decided")
    assert api.get(f"/api/bot/missions/{mission_id}/quotes", headers=as_whatsapp()).json()["money"]["dispute_offers"] == []
