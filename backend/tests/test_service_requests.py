"""Services proposés par les prestataires : créés au nom du prestataire,
listés pour lui, décidés une seule fois par un admin."""

from backend.tests.test_main import _as, _authed_client, _grant_admin, _register_provider, _reload_backend_with_db

ADMIN = 999


def _backend(monkeypatch, backend_db_url):
    backend_main, database_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    _grant_admin(database_module, ADMIN)
    return _authed_client(backend_main)


def _propose(test_client, telegram_id, service_name="Soudure industrielle", description="Soudure à l'arc et réparation de portails."):
    return test_client.post(
        "/api/bot/service-requests",
        json={"service_name": service_name, "description": description},
        headers=_as(telegram_id),
    )


def test_create_service_request_nominal(tmp_path, monkeypatch, backend_db_url):
    with _backend(monkeypatch, backend_db_url) as test_client:
        _register_provider(test_client, 1001, ["service_plomberie"], ["Gombe"], full_name="Jean Prestataire")

        response = _propose(test_client, 1001, service_name="  Soudure industrielle  ")

        assert response.status_code == 200
        request = response.json()["service_request"]
        assert request["id"] > 0
        assert request["provider_telegram_id"] == 1001
        assert request["service_name"] == "Soudure industrielle"
        assert request["status"] == "pending"


def test_create_service_request_provider_not_found(tmp_path, monkeypatch, backend_db_url):
    with _backend(monkeypatch, backend_db_url) as test_client:
        response = _propose(test_client, 999999)
        assert response.status_code == 404
        assert response.json()["detail"] == {"code": "provider_not_found"}


def test_a_proposal_needs_a_name_and_a_description(tmp_path, monkeypatch, backend_db_url):
    with _backend(monkeypatch, backend_db_url) as test_client:
        _register_provider(test_client, 1001, ["service_plomberie"], ["Gombe"])
        assert _propose(test_client, 1001, service_name="  ab ").status_code == 422
        assert _propose(test_client, 1001, description="Court").status_code == 422
        assert test_client.get("/api/me/service-requests", headers=_as(1001)).json()["service_requests"] == []


def test_a_provider_lists_only_his_own_proposals(tmp_path, monkeypatch, backend_db_url):
    with _backend(monkeypatch, backend_db_url) as test_client:
        _register_provider(test_client, 4001, ["service_nettoyage"], ["Limete"])
        _register_provider(test_client, 4002, ["service_nettoyage"], ["Limete"])
        _propose(test_client, 4001, "Peinture époxy", "Revêtement sols industriels et résine.")
        _propose(test_client, 4002, "Menuiserie aluminium", "Portes et fenêtres sur mesure.")

        mine = test_client.get("/api/me/service-requests", headers=_as(4001)).json()["service_requests"]
        assert [(request["service_name"], request["status"]) for request in mine] == [("Peinture époxy", "pending")]
        assert test_client.get("/api/me/service-requests", headers=_as(555)).status_code == 404


def test_pending_proposals_are_listed_for_the_admin_only(tmp_path, monkeypatch, backend_db_url):
    with _backend(monkeypatch, backend_db_url) as test_client:
        for telegram_id, name in ((2001, "Alice"), (2002, "Bob")):
            _register_provider(test_client, telegram_id, ["service_electricite"], ["Kalamu"], full_name=name)
        _propose(test_client, 2001, "Domotique", "Installation d'équipements connectés.")
        _propose(test_client, 2002, "Menuiserie aluminium", "Portes et fenêtres sur mesure.")

        assert test_client.get("/api/admin/service-requests", headers=_as(2001)).status_code == 403
        response = test_client.get("/api/admin/service-requests", headers=_as(ADMIN))
        assert [request["provider_name"] for request in response.json()["service_requests"]] == ["Alice", "Bob"]
        assert test_client.get("/api/admin/stats", headers=_as(ADMIN)).json()["stats"]["pending_services"] == 2


def test_a_proposal_is_decided_once(tmp_path, monkeypatch, backend_db_url):
    with _backend(monkeypatch, backend_db_url) as test_client:
        _register_provider(test_client, 3001, ["service_climatisation"], ["Kalamu"], full_name="Charlie")
        request_id = _propose(test_client, 3001, "Frigoriste", "Réparation chambres froides.").json()["service_request"]["id"]

        def decide(status, actor=ADMIN):
            return test_client.patch(
                f"/api/admin/service-requests/{request_id}", json={"status": status, "admin_note": "Validé"}, headers=_as(actor)
            )

        assert decide("accepted", actor=3001).status_code == 403
        assert decide("unknown").status_code == 400
        accepted = decide("accepted")
        assert accepted.status_code == 200
        assert accepted.json()["service_request"]["status"] == "accepted"
        assert accepted.json()["service_request"]["admin_note"] == "Validé"
        assert decide("rejected").status_code == 409
        assert test_client.get("/api/admin/service-requests", headers=_as(ADMIN)).json()["service_requests"] == []
