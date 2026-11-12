"""Lieu exact de la mission (CONCEPTION_MISSIONS.md, « Lieu exact de la mission »).

Le point et le repère sont obligatoires à la création, vérifiés par le
backend, jamais renvoyés avec la mission, et lus par une route à part : le
client et l'admin toujours, le prestataire choisi seulement une fois la
mission payée et tant qu'il doit s'y rendre ou y travailler."""

import pytest
from sqlalchemy.exc import IntegrityError

from backend.tests.test_main import _as, _authed_client, _register_provider, _reload_backend_with_db

CLIENT = 42
PROVIDER = 7
OTHER_PROVIDER = 8
STRANGER = 555
ADMIN = 999
GOMBE = {"latitude": -4.30761234, "longitude": 15.31251234, "landmark": "  Portail bleu   après la poste "}


def _backend(monkeypatch, tmp_path):
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", str(ADMIN))
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    return _authed_client(backend_main), database_module


def _create(test_client, key="demande-1", destination=GOMBE, **fields):
    payload = {
        "creation_key": key,
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Fuite sous l'évier",
        "urgent": False,
        "alert_provider_telegram_ids": [PROVIDER, OTHER_PROVIDER],
        **fields,
    }
    if destination is not None:
        payload["destination"] = destination
    return test_client.post("/api/bot/missions", json=payload, headers=_as(CLIENT))


def _destination(test_client, mission_id, actor):
    return test_client.get(f"/api/bot/missions/{mission_id}/destination", headers=_as(actor))


def _quote(test_client, mission_id, provider):
    response = test_client.post(
        "/api/bot/quotes",
        json={"mission_id": mission_id, "amount": 50.0, "currency": "USD", "delay_hours": 2},
        headers=_as(provider),
    )
    assert response.status_code == 200, response.json()
    return response.json()["quote"]["id"]


def _pay(test_client, database_module, mission_id, quote_id):
    from backend.app import ledger

    with database_module.SessionLocal() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, CLIENT, create=True)
        ledger.record_opening_balance(db, account_id, "USD", 100)
        db.commit()
    response = test_client.post(
        f"/api/bot/missions/{mission_id}/fund", json={"method": "wallet", "quote_id": quote_id}, headers=_as(CLIENT)
    )
    assert response.status_code == 200, response.json()


def test_the_destination_is_stored_cleaned_and_never_sent_with_the_mission(tmp_path, monkeypatch):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        created = _create(test_client)
        mission_id = created.json()["mission"]["mission_id"]
        read = test_client.get(f"/api/bot/missions/{mission_id}", headers=_as(CLIENT))

    assert created.status_code == 200
    for body in (created.json(), read.json()):
        assert "destination" not in str(body), "le lieu a sa propre route, jamais la vue de la mission"
        assert "15.3125" not in str(body)

    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        stored = db.get(BotMission, mission_id)
        assert (stored.destination_latitude, stored.destination_longitude) == (-4.307612, 15.312512)
        assert stored.destination_landmark == "Portail bleu après la poste"


@pytest.mark.parametrize(
    "destination, code",
    [
        ({"latitude": 0.0, "longitude": 0.0, "landmark": "Chez moi"}, "destination_outside_service_area"),
        ({"latitude": -11.66, "longitude": 27.48, "landmark": "Lubumbashi"}, "destination_outside_service_area"),
        ({"latitude": -4.30, "longitude": 15.31, "landmark": "  a "}, "invalid_destination"),
        ({"latitude": -4.30, "longitude": 15.31, "landmark": "x" * 301}, "invalid_destination"),
    ],
)
def test_a_wrong_destination_is_refused_and_creates_nothing(tmp_path, monkeypatch, destination, code):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        refused = _create(test_client, destination=destination)
        # La même clé, avec un lieu corrigé, crée bien la mission : le refus
        # n'a rien enregistré.
        corrected = _create(test_client)

    assert refused.status_code == 400
    assert refused.json()["detail"] == {"code": code}
    assert corrected.status_code == 200 and corrected.json()["created"] is True


def test_the_destination_is_mandatory(tmp_path, monkeypatch):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        missing = _create(test_client, destination=None)
        no_landmark = _create(test_client, destination={"latitude": -4.3, "longitude": 15.3})

    assert missing.status_code == 422
    assert no_landmark.status_code == 422

    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        assert db.query(BotMission).count() == 0


def test_a_replay_with_another_destination_is_refused(tmp_path, monkeypatch):
    test_client, _ = _backend(monkeypatch, tmp_path)
    with test_client:
        first = _create(test_client)
        replay = _create(test_client)
        moved = _create(test_client, destination={**GOMBE, "latitude": -4.33})
        new_landmark = _create(test_client, destination={**GOMBE, "landmark": "Autre repère"})

    assert replay.json()["created"] is False
    assert replay.json()["mission"]["mission_id"] == first.json()["mission"]["mission_id"]
    assert moved.json()["detail"] == {"code": "creation_key_reused"}
    assert new_landmark.json()["detail"] == {"code": "creation_key_reused"}


def test_who_reads_the_destination_along_the_mission(tmp_path, monkeypatch):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        _register_provider(test_client, PROVIDER, ["service_plomberie"], ["Gombe"])
        _register_provider(test_client, OTHER_PROVIDER, ["service_plomberie"], ["Gombe"])
        mission_id = _create(test_client).json()["mission"]["mission_id"]

        def status(actor):
            return _destination(test_client, mission_id, actor).status_code

        granted = _destination(test_client, mission_id, CLIENT)
        assert granted.status_code == 200
        assert granted.json()["destination"] == {
            "latitude": -4.307612,
            "longitude": 15.312512,
            "landmark": "Portail bleu après la poste",
        }
        assert status(ADMIN) == 200
        # Prévenu : il lit la mission (et sa commune), pas encore le lieu.
        assert status(PROVIDER) == 403
        assert _destination(test_client, mission_id, PROVIDER).json()["detail"] == {"code": "destination_not_available"}
        # Inconnu : même réponse qu'un numéro inexistant.
        assert status(STRANGER) == 404
        assert (
            _destination(test_client, mission_id, STRANGER).json()
            == _destination(test_client, 4242, STRANGER).json()
            == {"detail": {"code": "mission_not_found"}}
        )

        quote_id = _quote(test_client, mission_id, PROVIDER)
        _quote(test_client, mission_id, OTHER_PROVIDER)
        assert status(PROVIDER) == 403, "un devis envoyé ne donne pas le lieu"

        accepted = test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(CLIENT))
        assert accepted.status_code == 200
        assert status(PROVIDER) == 403, "devis accepté mais mission pas encore payée"

        _pay(test_client, database_module, mission_id, quote_id)
        assert status(PROVIDER) == 200, "mission payée : le prestataire choisi sait où aller"
        assert status(OTHER_PROVIDER) == 403, "l'autre prestataire n'a jamais le lieu"

        assert test_client.post(f"/api/bot/missions/{mission_id}/presence/confirm", headers=_as(CLIENT)).status_code == 200
        assert status(PROVIDER) == 200, "en cours d'intervention"

        assert test_client.post(f"/api/bot/missions/{mission_id}/finish", headers=_as(PROVIDER)).status_code == 200
        assert status(PROVIDER) == 403, "intervention terminée : le lieu n'est plus montré"
        assert status(CLIENT) == 200 and status(ADMIN) == 200


def test_a_disputed_mission_hides_the_destination_from_the_provider(tmp_path, monkeypatch):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        _register_provider(test_client, PROVIDER, ["service_plomberie"], ["Gombe"])
        mission_id = _create(test_client).json()["mission"]["mission_id"]
        quote_id = _quote(test_client, mission_id, PROVIDER)
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(CLIENT))
        _pay(test_client, database_module, mission_id, quote_id)
        disputed = test_client.post(
            f"/api/bot/missions/{mission_id}/dispute", json={"reason": "Jamais venu"}, headers=_as(CLIENT)
        )
        assert disputed.status_code == 200
        assert _destination(test_client, mission_id, PROVIDER).status_code == 403
        assert _destination(test_client, mission_id, CLIENT).status_code == 200


def test_a_mission_created_before_the_exact_place_says_so(tmp_path, monkeypatch):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        mission_id = _create(test_client).json()["mission"]["mission_id"]

        from backend.app.models import BotMission

        with database_module.SessionLocal() as db:
            mission = db.get(BotMission, mission_id)
            mission.destination_latitude = mission.destination_longitude = mission.destination_landmark = None
            db.commit()

        response = _destination(test_client, mission_id, CLIENT)

    assert response.status_code == 404
    assert response.json()["detail"] == {"code": "destination_unknown"}


def test_the_database_refuses_a_partial_destination(tmp_path, monkeypatch):
    test_client, database_module = _backend(monkeypatch, tmp_path)
    with test_client:
        mission_id = _create(test_client).json()["mission"]["mission_id"]

    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        db.get(BotMission, mission_id).destination_landmark = None
        with pytest.raises(IntegrityError):
            db.commit()
