"""Missions créées et lues par le backend, seule mémoire des missions.

Le backend attribue le numéro, le client est l'acteur, les prestataires
prévenus sont enregistrés avec la mission, et seuls les intéressés la lisent."""

from backend.tests.test_main import TEST_API_KEY, _as, _authed_client, _grant_admin, _register_provider, _reload_backend_with_db

CLIENT = 42
PROVIDER = 7
OTHER_PROVIDER = 8
STRANGER = 555
ADMIN = 999


def _create(test_client, client=CLIENT, key="demande-1", **fields):
    payload = {
        "creation_key": key,
        "service": "service_plomberie",
        "commune": "Gombe",
        "currency": "USD",
        "description": "Fuite sous l'évier",
        "urgent": False,
        "media": [{"kind": "photo", "id": "photo-a"}, {"kind": "voice", "id": "voix-a"}],
        "destination": {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"},
        **fields,
    }
    return test_client.post("/api/bot/missions", json=payload, headers=_as(client))


def _backend(monkeypatch, backend_db_url):
    """Backend jetable avec un admin et un plombier vérifié à Gombe
    (`PROVIDER`), que le backend prévient donc des missions de plomberie."""
    backend_main, database_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    _grant_admin(database_module, ADMIN)
    test_client = _authed_client(backend_main)
    _register_provider(test_client, PROVIDER, ["service_plomberie"], ["Gombe"])
    return test_client, database_module


def test_the_backend_numbers_the_mission_and_records_media_and_alerts(tmp_path, monkeypatch, backend_db_url):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        # Le client est aussi plombier à Gombe : jamais prévenu de sa propre mission.
        _register_provider(test_client, CLIENT, ["service_plomberie"], ["Gombe"])
        first = _create(test_client)
        second = _create(test_client, key="demande-2")

    assert first.status_code == 200
    body = first.json()
    assert body["created"] is True
    assert body["viewer_role"] == "client"
    mission = body["mission"]
    assert second.json()["mission"]["mission_id"] == mission["mission_id"] + 1
    assert mission["telegram_id"] == CLIENT
    assert mission["status"] == "pending"
    assert mission["media"] == [
        {"channel": "telegram", "kind": "photo", "id": "photo-a"},
        {"channel": "telegram", "kind": "voice", "id": "voix-a"},
    ]
    assert body["alerted_provider_telegram_ids"] == [PROVIDER]

    from backend.app import ledger
    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        stored = db.get(BotMission, mission["mission_id"])
        assert stored.client_account_id == ledger.account_id_for(db, ledger.TELEGRAM, CLIENT)


def test_the_backend_alerts_the_three_best_providers_who_can_do_the_job(tmp_path, monkeypatch, backend_db_url):
    """Le canal ne propose personne : le backend prévient au plus trois
    prestataires vérifiés, disponibles, non suspendus, qui font ce service
    dans cette commune, du mieux classé au moins bien classé."""
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        for telegram_id in (11, 12, 13):
            _register_provider(test_client, telegram_id, ["service_plomberie"], ["Gombe"])
        _register_provider(test_client, 20, ["service_plomberie"], ["Gombe"], verified=False)
        _register_provider(test_client, 21, ["service_plomberie"], ["Lemba"])
        _register_provider(test_client, 22, ["service_nettoyage"], ["Gombe"])
        _register_provider(test_client, 23, ["service_plomberie"], ["Gombe"])
        assert test_client.patch("/api/me/provider-profile/status", json={"status": "offline"}, headers=_as(23)).status_code == 200
        _register_provider(test_client, 24, ["service_plomberie"], ["Gombe"])
        suspended = test_client.get("/api/me/profile", headers=_as(24)).json()["account_id"]
        assert test_client.post(f"/api/admin/providers/{suspended}/suspend", headers=_as(ADMIN)).status_code == 200

        from backend.tests.profils_de_test import provider_of

        with database_module.SessionLocal() as db:
            provider_of(db, 13).badge = "partner"
            provider_of(db, 12).average_rating = 2.0
            db.commit()

        body = _create(test_client).json()
        plumbing_elsewhere = _create(test_client, key="demande-2", commune="Lemba").json()
        nobody = _create(test_client, key="demande-3", service="service_jardinage").json()
        unknown = _create(test_client, key="demande-4", service="service_inconnu")
        unserved = _create(test_client, key="demande-5", commune="Paris")

    # 13 (badge partenaire, 30 points) puis 12 (note 2, 25 points) puis le plus ancien inscrit des
    # autres à égalité (PROVIDER) ; 11 n'est pas prévenu (trois au plus).
    assert body["alerted_provider_telegram_ids"] == [13, 12, PROVIDER]
    assert plumbing_elsewhere["alerted_provider_telegram_ids"] == [21]
    assert nobody["alerted_provider_telegram_ids"] == []
    # Service ou commune hors catalogue : refus, rien n'est créé.
    assert unknown.json()["detail"] == {"code": "invalid_mission"}
    assert unserved.json()["detail"] == {"code": "invalid_mission"}

    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        assert db.query(BotMission).count() == 3


def test_a_replayed_creation_returns_the_same_mission_and_a_different_one_is_refused(tmp_path, monkeypatch, backend_db_url):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        first = _create(test_client).json()
        replay = _create(test_client)
        changed = _create(test_client, description="Autre chose")
        other_client = _create(test_client, client=43)

    assert replay.status_code == 200
    assert replay.json()["created"] is False
    assert replay.json()["mission"]["mission_id"] == first["mission"]["mission_id"]
    assert changed.status_code == 409
    assert changed.json()["detail"] == {"code": "creation_key_reused"}
    # La clé n'est unique que pour un même client.
    assert other_client.status_code == 200
    assert other_client.json()["mission"]["mission_id"] != first["mission"]["mission_id"]

    from backend.app.models import BotMission, MissionAlert, MissionMedia

    with database_module.SessionLocal() as db:
        assert db.query(BotMission).count() == 2
        assert db.query(MissionMedia).count() == 4
        assert db.query(MissionAlert).count() == 2


def test_invalid_creation_requests_are_refused_and_write_nothing(tmp_path, monkeypatch, backend_db_url):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        assert _create(test_client, currency="EUR").json()["detail"] == {"code": "invalid_currency"}
        assert _create(test_client, media=[{"kind": "video", "id": "x"}]).json()["detail"] == {"code": "invalid_media"}
        assert _create(test_client, media=[{"kind": "photo", "id": str(n)} for n in range(21)]).status_code == 422
        assert _create(test_client, service="").status_code == 422
        no_actor = test_client.post(
            "/api/bot/missions", json={"creation_key": "k", "service": "s", "commune": "Gombe"}
        )
        assert no_actor.json()["detail"] == {"code": "actor_required"}
        # L'ancien contrat (numéro et client choisis par le canal) n'existe plus.
        old = test_client.post(
            "/api/bot/missions",
            json={"telegram_id": CLIENT, "mission_id": 1001, "service": "s", "commune": "Gombe"},
            headers=_as(CLIENT),
        )
        assert old.status_code == 422

    from backend.app.models import BotMission

    with database_module.SessionLocal() as db:
        assert db.query(BotMission).count() == 0


def test_a_telegram_video_note_is_kept_with_the_mission(tmp_path, monkeypatch, backend_db_url):
    test_client, _ = _backend(monkeypatch, backend_db_url)
    with test_client:
        created = _create(test_client, media=[{"kind": "video_note", "id": "rond-1"}])

    assert created.status_code == 200
    assert created.json()["mission"]["media"] == [{"channel": "telegram", "kind": "video_note", "id": "rond-1"}]


def test_only_the_people_concerned_read_a_mission(tmp_path, monkeypatch, backend_db_url):
    test_client, _ = _backend(monkeypatch, backend_db_url)
    with test_client:
        _register_provider(test_client, PROVIDER, ["service_plomberie"], ["Gombe"])
        mission_id = _create(test_client).json()["mission"]["mission_id"]

        def read(actor):
            return test_client.get(f"/api/bot/missions/{mission_id}", headers=_as(actor))

        client_view = read(CLIENT).json()
        assert client_view["viewer_role"] == "client"
        assert client_view["alerted_provider_telegram_ids"] == [PROVIDER]

        alerted_view = read(PROVIDER).json()
        assert alerted_view["viewer_role"] == "alerted"
        assert "alerted_provider_telegram_ids" not in alerted_view, "un prestataire ne voit pas ses concurrents"

        # Un inconnu reçoit la même réponse que pour un numéro inexistant.
        assert read(STRANGER).status_code == 404
        assert read(STRANGER).json() == test_client.get("/api/bot/missions/4242", headers=_as(STRANGER)).json()
        assert read(ADMIN).json()["viewer_role"] == "admin"
        assert test_client.get(f"/api/bot/missions/{mission_id}").json()["detail"] == {"code": "actor_required"}

        quote = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 50.0, "currency": "USD", "delay_hours": 2},
            headers=_as(PROVIDER),
        )
        assert quote.status_code == 200
        assert read(PROVIDER).json()["viewer_role"] == "provider"


def test_only_an_alerted_provider_can_quote(tmp_path, monkeypatch, backend_db_url):
    test_client, _ = _backend(monkeypatch, backend_db_url)
    with test_client:
        mission_id = _create(test_client).json()["mission"]["mission_id"]
        response = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mission_id, "amount": 50.0, "currency": "USD", "delay_hours": 2},
            headers=_as(OTHER_PROVIDER),
        )

    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "provider_not_alerted"}


def test_my_missions_lists_only_what_is_mine(tmp_path, monkeypatch, backend_db_url):
    test_client, _ = _backend(monkeypatch, backend_db_url)
    with test_client:
        mine = _create(test_client).json()["mission"]["mission_id"]
        _create(test_client, client=43, key="autre")
        quote_id = test_client.post(
            "/api/bot/quotes",
            json={"mission_id": mine, "amount": 50.0, "currency": "USD", "delay_hours": 2},
            headers=_as(PROVIDER),
        ).json()["quote"]["id"]
        test_client.post(f"/api/bot/quotes/{quote_id}/accept", headers=_as(CLIENT))

        def listed(actor, role):
            response = test_client.get(f"/api/me/missions?role={role}", headers=_as(actor))
            return [mission["mission_id"] for mission in response.json()["missions"]]

        assert listed(CLIENT, "client") == [mine]
        assert listed(CLIENT, "provider") == []
        assert listed(PROVIDER, "provider") == [mine]
        assert listed(PROVIDER, "client") == []
        assert listed(STRANGER, "client") == []
        assert test_client.get("/api/me/missions?role=admin", headers=_as(CLIENT)).status_code == 400


def test_admin_lists_and_counts_missions(tmp_path, monkeypatch, backend_db_url):
    test_client, database_module = _backend(monkeypatch, backend_db_url)
    with test_client:
        first = _create(test_client).json()["mission"]["mission_id"]
        second = _create(test_client, key="demande-2").json()["mission"]["mission_id"]

        from backend.app.models import BotMission

        with database_module.SessionLocal() as db:
            db.get(BotMission, first).status = "disputed"
            db.commit()

        assert test_client.get("/api/admin/missions", headers=_as(CLIENT)).status_code == 403
        assert test_client.get("/api/admin/stats", headers=_as(CLIENT)).status_code == 403

        recent = test_client.get("/api/admin/missions", headers=_as(ADMIN)).json()["missions"]
        assert [mission["mission_id"] for mission in recent] == [second, first]
        disputed = test_client.get("/api/admin/missions?status=disputed", headers=_as(ADMIN)).json()["missions"]
        assert [mission["mission_id"] for mission in disputed] == [first]
        assert test_client.get("/api/admin/stats", headers=_as(ADMIN)).json()["stats"] == {
            "missions": 2,
            "disputes": 1,
            "users": 0,
            "providers": 1,
            "providers_pending": 0,
            "pending_services": 0,
        }


def test_api_key_is_still_required(tmp_path, monkeypatch, backend_db_url):
    test_client, _ = _backend(monkeypatch, backend_db_url)
    with test_client:
        del test_client.headers["X-API-Key"]
        assert _create(test_client).status_code == 401
    assert TEST_API_KEY
