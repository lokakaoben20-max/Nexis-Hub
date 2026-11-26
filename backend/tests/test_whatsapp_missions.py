"""Missions créées depuis WhatsApp (étape 5) : parité avec Telegram.

Un client WhatsApp n'a pas de Telegram : sa mission est rattachée à son
compte Nexis. Les mêmes réponses donnent la même mission en base, quel que
soit le canal ; un message rejoué ou un double appui n'en crée qu'une.
"""

import importlib
import uuid

import pytest
from fastapi.testclient import TestClient

from backend.tests.test_whatsapp_channel import (
    BSUID,
    OTHER_BSUID,
    TELEGRAM_KEY,
    WHATSAPP_KEY,
    as_telegram,
    as_whatsapp,
    register,
)

PROVIDER = 7
DESTINATION = {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"}


@pytest.fixture
def backend(backend_db_url, monkeypatch):
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    main.database = database
    from backend.app import tasks

    monkeypatch.setattr(tasks, "SessionLocal", database.SessionLocal)
    return main


@pytest.fixture
def api(backend):
    with TestClient(backend.app) as test_client:
        yield test_client


def verified_provider(api, backend, telegram_id=PROVIDER, service="service_nettoyage", commune="Gombe"):
    payload = {
        "full_name": f"Prestataire {telegram_id}",
        "phone_number": "+243800000000",
        "services": [service],
        "communes": [commune],
    }
    response = api.put("/api/me/provider-profile", json=payload, headers=as_telegram(telegram_id))
    assert response.status_code == 200, response.json()
    from backend.app import profils

    with backend.database.SessionLocal() as db:
        profils.verify_provider(db, response.json()["account_id"])
        db.commit()
    assert api.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=as_telegram(telegram_id)).status_code == 200


def request_body(creation_key="demande-1", **fields):
    return {
        "creation_key": creation_key,
        "service": "service_nettoyage",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Nettoyer le salon et la cuisine",
        "urgent": True,
        "destination": DESTINATION,
        **fields,
    }


def create_on_whatsapp(api, body, key=None, bsuid=BSUID):
    headers = {**as_whatsapp(bsuid), "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}"}
    return api.post("/api/bot/missions", json=body, headers=headers)


def stored_missions(backend):
    from backend.app.models import BotMission

    with backend.database.SessionLocal() as db:
        return [
            {
                "service": mission.service,
                "commune": mission.commune,
                "currency": mission.currency,
                "description": mission.description,
                "urgent": mission.urgent,
                "status": mission.status,
                "destination": (mission.destination_latitude, mission.destination_longitude, mission.destination_landmark),
                "telegram_id": mission.telegram_id,
                "client_account_id": mission.client_account_id,
            }
            for mission in db.query(BotMission).order_by(BotMission.mission_id)
        ]


def alerts_written(backend):
    from backend.app.models import Notification

    with backend.database.SessionLocal() as db:
        return [row.event_key for row in db.query(Notification).filter(Notification.message_key == "new_mission_alert")]


def account_of(api, headers):
    return api.get("/api/me/profile", headers=headers).json()["account_id"]


def test_the_same_answers_give_the_same_mission_on_both_channels(api, backend):
    verified_provider(api, backend)
    assert register(api).status_code == 200
    assert api.put("/api/me/client-profile", json={"first_name": "Mado"}, headers=as_telegram(42)).status_code == 200

    on_whatsapp = create_on_whatsapp(api, request_body())
    on_telegram = api.post("/api/bot/missions", json=request_body(), headers=as_telegram(42))

    assert on_whatsapp.status_code == on_telegram.status_code == 200
    whatsapp_row, telegram_row = stored_missions(backend)
    # Même mission ; seul le client diffère (son compte, et Telegram pour le client Telegram).
    assert whatsapp_row["telegram_id"] is None
    assert whatsapp_row["client_account_id"] == account_of(api, as_whatsapp())
    assert telegram_row["telegram_id"] == 42
    assert telegram_row["client_account_id"] == account_of(api, as_telegram(42))
    for row in (whatsapp_row, telegram_row):
        del row["telegram_id"], row["client_account_id"]
    assert whatsapp_row == telegram_row
    assert whatsapp_row["status"] == "pending"
    # Le prestataire est prévenu des deux, sur Telegram.
    assert len(alerts_written(backend)) == 2
    assert on_whatsapp.json()["alerted_provider_count"] == on_telegram.json()["alerted_provider_count"] == 1


def test_a_whatsapp_client_never_sees_the_telegram_ids_of_providers(api, backend):
    verified_provider(api, backend)
    register(api)
    body = create_on_whatsapp(api, request_body()).json()
    assert "alerted_provider_telegram_ids" not in body
    assert body["mission"]["telegram_id"] is None
    assert body["alerted_provider_count"] == 1
    assert str(PROVIDER) not in repr(body)


def test_a_replayed_message_returns_the_same_answer_and_creates_one_mission(api, backend):
    verified_provider(api, backend)
    register(api)
    key = f"wamid.{uuid.uuid4().hex}"
    first = create_on_whatsapp(api, request_body(), key=key)
    replay = create_on_whatsapp(api, request_body(), key=key)
    assert first.status_code == replay.status_code == 200
    assert replay.headers.get("Idempotent-Replayed") == "true"
    assert replay.json() == first.json()
    assert len(stored_missions(backend)) == 1
    assert len(alerts_written(backend)) == 1


def test_a_double_tap_on_confirm_creates_one_mission(api, backend):
    """Deux appuis = deux messages (deux clés) mais la même demande
    (`creation_key`) : une mission, une alerte."""
    verified_provider(api, backend)
    register(api)
    first = create_on_whatsapp(api, request_body())
    second = create_on_whatsapp(api, request_body())
    assert (first.json()["created"], second.json()["created"]) == (True, False)
    assert first.json()["mission"]["mission_id"] == second.json()["mission"]["mission_id"]
    assert len(stored_missions(backend)) == 1
    assert len(alerts_written(backend)) == 1


def test_the_same_creation_key_with_another_request_is_refused(api, backend):
    register(api)
    assert create_on_whatsapp(api, request_body()).status_code == 200
    changed = create_on_whatsapp(api, request_body(description="Autre chose à faire"))
    assert (changed.status_code, changed.json()["detail"]["code"]) == (409, "creation_key_reused")


def test_two_whatsapp_clients_may_use_the_same_creation_key(api, backend):
    register(api)
    register(api, bsuid=OTHER_BSUID, phone="243810000002")
    assert create_on_whatsapp(api, request_body()).json()["created"] is True
    assert create_on_whatsapp(api, request_body(), bsuid=OTHER_BSUID).json()["created"] is True
    assert len(stored_missions(backend)) == 2


def test_a_whatsapp_write_needs_its_message_key(api, backend):
    register(api)
    response = api.post("/api/bot/missions", json=request_body(), headers=as_whatsapp())
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "idempotency_key_required")
    assert stored_missions(backend) == []


@pytest.mark.parametrize(
    "destination, code",
    [
        ({"latitude": 48.8566, "longitude": 2.3522, "landmark": "Tour Eiffel"}, "destination_outside_service_area"),
        ({"latitude": -4.3076, "longitude": 15.3125, "landmark": "  "}, "invalid_destination"),
    ],
)
def test_a_place_outside_kinshasa_or_without_landmark_is_refused(api, backend, destination, code):
    register(api)
    response = create_on_whatsapp(api, request_body(destination=destination))
    assert (response.status_code, response.json()["detail"]["code"]) == (400, code)
    assert stored_missions(backend) == []


def test_a_refused_request_can_be_corrected_under_the_same_creation_key(api, backend):
    """Rien n'est écrit sur un refus : le client corrige le lieu et confirme
    à nouveau avec la même demande."""
    register(api)
    outside = {"latitude": 48.8566, "longitude": 2.3522, "landmark": "Tour Eiffel"}
    assert create_on_whatsapp(api, request_body(destination=outside)).status_code == 400
    assert create_on_whatsapp(api, request_body()).json()["created"] is True


def test_other_service_is_not_a_mission_on_whatsapp_either(api, backend):
    register(api)
    response = create_on_whatsapp(api, request_body(service="service_autre"))
    assert (response.status_code, response.json()["detail"]["code"]) == (400, "service_not_requestable")


def test_a_whatsapp_client_is_never_alerted_of_their_own_mission(api, backend):
    """Un client WhatsApp n'est jamais prestataire : seul le prestataire
    Telegram est prévenu."""
    verified_provider(api, backend)
    register(api)
    create_on_whatsapp(api, request_body())
    from backend.app.models import Notification

    with backend.database.SessionLocal() as db:
        recipients = {row.recipient_account_id for row in db.query(Notification)}
    assert account_of(api, as_whatsapp()) not in recipients
    assert recipients == {account_of(api, as_telegram(PROVIDER))}
