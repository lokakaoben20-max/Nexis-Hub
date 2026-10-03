"""Routes d'acceptation des conditions et contrôle au paiement
(CONCEPTION_ACCEPTATIONS.md)."""

from datetime import timedelta

from backend.tests.test_main import _authed_client, _fund, _reload_backend_with_db

CLIENT = 42


def _publish(database_module, key, version="v1", effective_in=timedelta(0)):
    from backend.app import ledger, legal

    with database_module.SessionLocal() as db:
        legal.publish_version(db, key, version, f"https://exemple.test/{key}/{version}", b"Texte", ledger._utcnow() + effective_in)
        db.commit()


def _publish_client_documents(database_module, version="v1", effective_in=timedelta(0)):
    from backend.app import legal

    for key in (legal.GENERAL_TERMS, legal.DATA_CONSENT):
        _publish(database_module, key, version, effective_in)


def _decide(test_client, key, version="v1", decision="accepted", external_id=str(CLIENT)):
    return test_client.post(
        "/api/bot/legal/decisions",
        json={
            "channel": "telegram",
            "external_id": external_id,
            "document_key": key,
            "version": version,
            "decision": decision,
            "language": "fr",
        },
    )


def _status(test_client, role="client", external_id=str(CLIENT)):
    return test_client.get("/api/bot/legal/status", params={"channel": "telegram", "external_id": external_id, "role": role})


def test_status_lists_missing_documents_in_order(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _publish_client_documents(database_module)
    with _authed_client(backend_main) as test_client:
        response = _status(test_client)
    assert response.status_code == 200
    body = response.json()
    assert body["complete"] is False
    assert [item["document_key"] for item in body["missing"]] == ["conditions_generales", "donnees_transferts"]
    assert body["missing"][0]["url"] == "https://exemple.test/conditions_generales/v1"


def test_accepting_completes_the_status(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _publish_client_documents(database_module)
    with _authed_client(backend_main) as test_client:
        first = _decide(test_client, "conditions_generales")
        second = _decide(test_client, "donnees_transferts")
        status = _status(test_client)
    assert first.status_code == 200
    assert first.json()["decision"] == "accepted"
    assert second.status_code == 200
    assert status.json() == {"status": "ok", "role": "client", "missing": [], "complete": True}


def test_refusals_carry_a_stable_code(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _publish(database_module, "conditions_generales", "v1", timedelta(days=-30))
    _publish(database_module, "conditions_generales", "v2")
    with _authed_client(backend_main) as test_client:
        outdated = _decide(test_client, "conditions_generales", "v1")
        unknown = _decide(test_client, "conditions_generales", "v9")
        bad_decision = _decide(test_client, "conditions_generales", "v2", decision="oui")
        bad_role = _status(test_client, role="admin")
    assert (outdated.status_code, outdated.json()["detail"]) == (409, {"code": "terms_version_outdated"})
    assert (unknown.status_code, unknown.json()["detail"]) == (404, {"code": "legal_version_not_found"})
    assert (bad_decision.status_code, bad_decision.json()["detail"]) == (422, {"code": "unknown_decision"})
    assert (bad_role.status_code, bad_role.json()["detail"]) == (422, {"code": "unknown_role"})


def test_routes_require_the_api_key(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)
    with TestClient(backend_main.app) as anonymous:
        assert _status(anonymous).status_code == 401
        assert _decide(anonymous, "conditions_generales").status_code == 401


def test_payment_works_while_nothing_is_published(tmp_path, monkeypatch):
    backend_main, _ = _reload_backend_with_db(monkeypatch, tmp_path)
    with _authed_client(backend_main) as test_client:
        response = _fund(test_client, client=CLIENT)
    assert response.status_code == 200


def test_payment_is_refused_until_the_client_accepts(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _publish_client_documents(database_module)
    with _authed_client(backend_main) as test_client:
        refused = _fund(test_client, client=CLIENT)
        _decide(test_client, "conditions_generales")
        still_refused = _fund(test_client, client=CLIENT)
        _decide(test_client, "donnees_transferts")
        accepted = _fund(test_client, client=CLIENT)
    assert refused.status_code == 409
    assert refused.json()["detail"]["code"] == "terms_not_accepted"
    assert still_refused.json()["detail"]["code"] == "terms_not_accepted"
    assert accepted.status_code == 200
    assert accepted.json()["mission"]["payment_status"] == "paid_escrow"

    from backend.app import ledger

    with database_module.SessionLocal() as db:
        # Aucun argent n'a bougé pendant les refus : un seul paiement.
        assert db.query(ledger.MoneyOperation).filter(ledger.MoneyOperation.kind != "opening_balance").count() == 1


def test_provider_terms_are_not_required_to_pay(tmp_path, monkeypatch):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _publish_client_documents(database_module)
    _publish(database_module, "conditions_prestataires")
    with _authed_client(backend_main) as test_client:
        _decide(test_client, "conditions_generales")
        _decide(test_client, "donnees_transferts")
        response = _fund(test_client, client=CLIENT)
    assert response.status_code == 200


def test_replaying_a_recorded_payment_is_not_blocked_by_a_new_version(tmp_path, monkeypatch):
    """Le rejeu d'un paiement déjà enregistré renvoie son résultat, même si
    une nouvelle version est entrée en vigueur entre-temps."""
    backend_main, database_module = _reload_backend_with_db(monkeypatch, tmp_path)
    _publish_client_documents(database_module, "v1", timedelta(days=-30))
    with _authed_client(backend_main) as test_client:
        _decide(test_client, "conditions_generales")
        _decide(test_client, "donnees_transferts")
        first = _fund(test_client, client=CLIENT)
        _publish_client_documents(database_module, "v2")
        replay = _fund(test_client, client=CLIENT)
        new_mission = _fund(test_client, mission_id=1002, client=CLIENT)
    assert first.status_code == 200
    assert replay.status_code == 200
    assert replay.json()["money"] == first.json()["money"]
    assert new_mission.status_code == 409
    assert new_mission.json()["detail"]["code"] == "terms_not_accepted"
