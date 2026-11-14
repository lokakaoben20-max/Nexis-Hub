"""Profils au backend, sur un vrai Postgres : migration f2a3b4c5d6e7 (reprise
des anciennes tables, échec sûr, retour arrière) et accès simultanés.

Même garde-fou que test_whatsapp_postgres.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import importlib
import json
import threading

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from backend.tests.test_whatsapp_postgres import URL, alembic, engine  # noqa: F401 (fixture)

REVISION = "f2a3b4c5d6e7"
PREVIOUS = "e1f2a3b4c5d6"
TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-0001"

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


def tables(engine):
    return set(inspect(engine).get_table_names())


def run(engine, sql, **params):
    with engine.begin() as connection:
        return connection.execute(text(sql), params)


def telegram_account(engine, telegram_id, language="fr", display_name=None):
    if display_name is None:
        account_id = run(
            engine, "INSERT INTO accounts (created_at, roles, language) VALUES (now(), '[]', :language) RETURNING id",
            language=language,
        ).scalar_one()
    else:  # avant la migration seulement : le nom WhatsApp était sur le compte
        account_id = run(
            engine,
            "INSERT INTO accounts (created_at, roles, language, display_name) VALUES (now(), '[]', :language, :name)"
            " RETURNING id",
            language=language,
            name=display_name,
        ).scalar_one()
    if telegram_id is not None:
        run(
            engine,
            "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at)"
            " VALUES (:account_id, 'telegram', :external_id, now(), now())",
            account_id=account_id,
            external_id=str(telegram_id),
        )
    return account_id


def old_provider(engine, telegram_id, *, status, verified, suspended=False, services=("service_plomberie",),
                 communes=("Gombe",), badge="pending", language="fr"):
    run(
        engine,
        "INSERT INTO bot_providers (telegram_id, full_name, phone_number, services, communes, language, status, module,"
        " badge, rating, total_missions, success_rate, is_verified, is_active, is_suspended, consecutive_ignored,"
        " average_rating, total_reviews, id_document_file_id, selfie_file_id, portfolio_file_ids)"
        " VALUES (:telegram_id, :name, '+243810000000', :services, :communes, :language, :status, 'B', :badge, 0, 4,"
        " 75.0, :verified, TRUE, :suspended, 2, 4.5, 3, 'piece', 'selfie', '[\"p1\"]')",
        telegram_id=telegram_id,
        name=f"Prestataire {telegram_id}",
        services=json.dumps(list(services)),
        communes=json.dumps(list(communes)),
        language=language,
        status=status,
        badge=badge,
        verified=verified,
        suspended=suspended,
    )


def account_of(engine, telegram_id):
    return run(
        engine,
        "SELECT account_id FROM channel_identities WHERE channel = 'telegram' AND external_id = :id",
        id=str(telegram_id),
    ).scalar_one()


def seed_old_profiles(engine):
    """Avant la migration : un client avec son compte, un client sans compte
    (ancienne ligne), des prestataires dans tous les états, un client WhatsApp."""
    telegram_account(engine, 1, language="ln")
    run(engine, "INSERT INTO bot_users VALUES (1, 'Ben', '+243810000001', 'ln', 0)")
    run(engine, "INSERT INTO bot_users VALUES (2, NULL, NULL, 'en', 0)")
    old_provider(engine, 3, status="available", verified=True, badge="premium",
                 services=("service_plomberie", "service_nettoyage"), communes=("Lemba", "Gombe"))
    old_provider(engine, 4, status="available", verified=False)  # disponible sans vérification
    old_provider(engine, 5, status="rejected", verified=False)
    old_provider(engine, 6, status="paused", verified=True, suspended=True)  # ancienne suspension
    old_provider(engine, 7, status="pending_verification", verified=True)  # incohérent
    old_provider(engine, 1, status="offline", verified=True, language="ln")  # client et prestataire
    telegram_account(engine, None, language="ln", display_name="Mado")  # client WhatsApp
    run(
        engine,
        "INSERT INTO bot_service_requests (id, provider_telegram_id, service_name, description, status, created_at)"
        " VALUES (11, 3, 'Frigoriste', 'Chambres froides', 'pending', now()),"
        " (12, 3, 'Peintre', '', 'accepted', now())",
    )


def test_upgrade_moves_every_profile_to_its_account(engine):
    alembic("upgrade", PREVIOUS)
    seed_old_profiles(engine)

    alembic("upgrade", REVISION)

    assert not {"bot_users", "bot_providers", "bot_service_requests"} & tables(engine)
    assert "display_name" not in {c["name"] for c in inspect(engine).get_columns("accounts")}
    assert run(engine, "SELECT COUNT(*) FROM services").scalar_one() == 9
    assert run(engine, "SELECT COUNT(*) FROM communes").scalar_one() == 9

    clients = dict(run(engine, "SELECT account_id, first_name FROM client_profiles").all())
    assert clients[account_of(engine, 1)] == "Ben"
    assert clients[account_of(engine, 2)] == "Client", "compte créé pour l'ancienne ligne sans compte"
    whatsapp = run(engine, "SELECT id FROM accounts WHERE id NOT IN (SELECT account_id FROM channel_identities)")
    assert clients[whatsapp.scalar_one()] == "Mado"
    assert run(engine, "SELECT language FROM accounts WHERE id = :id", id=account_of(engine, 2)).scalar_one() == "en"

    providers = {
        row.telegram_id: row
        for row in run(
            engine,
            "SELECT CAST(i.external_id AS BIGINT) AS telegram_id, p.* FROM provider_profiles p"
            " JOIN channel_identities i ON i.account_id = p.account_id AND i.channel = 'telegram'",
        ).all()
    }
    status = {telegram_id: (row.status, row.verified_at is not None, row.is_suspended) for telegram_id, row in providers.items()}
    assert status == {
        3: ("available", True, False),
        4: ("pending_verification", False, False),
        5: ("rejected", False, False),
        6: ("paused", True, True),
        7: ("offline", True, False),
        1: ("offline", True, False),
    }
    assert providers[3].badge == "premium" and providers[4].badge == "pending"
    assert (providers[3].average_rating, providers[3].total_missions, providers[3].consecutive_ignored) == (4.5, 4, 2)
    assert providers[3].portfolio_file_ids == ["p1"]
    services = run(
        engine, "SELECT service_key FROM provider_services WHERE account_id = :id ORDER BY service_key", id=account_of(engine, 3)
    ).scalars().all()
    assert services == ["service_nettoyage", "service_plomberie"]
    communes = run(
        engine, "SELECT commune FROM provider_communes WHERE account_id = :id ORDER BY commune", id=account_of(engine, 3)
    ).scalars().all()
    assert communes == ["Gombe", "Lemba"]

    roles = run(engine, "SELECT roles FROM accounts WHERE id = :id", id=account_of(engine, 1)).scalar_one()
    assert roles == ["client", "provider"]

    requests = run(engine, "SELECT id, provider_account_id, status, reviewed_at IS NOT NULL FROM provider_service_requests ORDER BY id").all()
    assert [tuple(row) for row in requests] == [(11, account_of(engine, 3), "pending", False), (12, account_of(engine, 3), "accepted", True)]
    next_id = run(
        engine,
        "INSERT INTO provider_service_requests (provider_account_id, service_name, description, status, created_at)"
        " VALUES (:id, 'x', '', 'pending', now()) RETURNING id",
        id=account_of(engine, 3),
    ).scalar_one()
    assert next_id == 13, "la séquence reprend après les numéros recopiés"


def test_an_unknown_service_stops_the_migration_and_changes_nothing(engine):
    alembic("upgrade", PREVIOUS)
    old_provider(engine, 3, status="available", verified=True, services=("service_peinture",), communes=("Kintambo",))

    with pytest.raises(RuntimeError, match="service_peinture.*Kintambo"):
        alembic("upgrade", REVISION)

    assert {"bot_providers", "bot_users"} <= tables(engine)
    assert "provider_profiles" not in tables(engine)
    assert run(engine, "SELECT version_num FROM alembic_version").scalar_one() == PREVIOUS
    assert run(engine, "SELECT COUNT(*) FROM bot_providers").scalar_one() == 1


def test_downgrade_restores_the_old_tables_then_upgrade_again(engine):
    alembic("upgrade", PREVIOUS)
    seed_old_profiles(engine)
    alembic("upgrade", REVISION)

    alembic("downgrade", PREVIOUS)

    assert {"bot_users", "bot_providers", "bot_service_requests"} <= tables(engine)
    assert "provider_profiles" not in tables(engine) and "services" not in tables(engine)
    users = dict(run(engine, "SELECT telegram_id, first_name FROM bot_users").all())
    assert users == {1: "Ben", 2: "Client"}
    assert run(engine, "SELECT display_name FROM accounts WHERE display_name IS NOT NULL").scalar_one() == "Mado"
    provider = run(engine, "SELECT * FROM bot_providers WHERE telegram_id = 3").mappings().one()
    assert provider["services"] == ["service_plomberie", "service_nettoyage"]
    assert (provider["status"], provider["is_verified"], provider["module"]) == ("available", True, "B")
    assert run(engine, "SELECT COUNT(*) FROM bot_service_requests").scalar_one() == 2

    alembic("upgrade", REVISION)
    assert run(engine, "SELECT COUNT(*) FROM provider_profiles").scalar_one() == 6


def test_downgrade_refuses_a_provider_without_telegram_identity(engine):
    alembic("upgrade", REVISION)
    account_id = telegram_account(engine, None)
    run(
        engine,
        "INSERT INTO provider_profiles (account_id, full_name, status, is_suspended, badge, average_rating,"
        " total_reviews, total_missions, success_rate, consecutive_ignored, portfolio_file_ids, created_at, updated_at)"
        " VALUES (:id, 'Sans Telegram', 'pending_verification', FALSE, 'pending', 0, 0, 0, 0, 0, '[]', now(), now())",
        id=account_id,
    )

    with pytest.raises(RuntimeError, match="sans identité Telegram"):
        alembic("downgrade", PREVIOUS)
    assert "provider_profiles" in tables(engine)


# --- Accès simultanés ----------------------------------------------------------


def _parallel(count, call):
    barrier = threading.Barrier(count)
    results = [None] * count
    errors = []

    def worker(index):
        barrier.wait()
        try:
            results[index] = call(index)
        except Exception as error:  # remonté au test
            errors.append(error)

    threads = [threading.Thread(target=worker, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert not errors, errors
    return results


@pytest.fixture
def sessions(engine):
    alembic("upgrade", "head")
    bound = create_engine(URL, future=True, pool_size=12)
    yield sessionmaker(bind=bound, autoflush=False, expire_on_commit=False)
    bound.dispose()


def test_simultaneous_declines_are_all_counted(sessions):
    from backend.app import ledger, profils

    with sessions() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, 7, create=True)
        profils.register_provider(
            db, account_id, full_name="Jean", phone_number=None, services=["service_plomberie"], communes=["Gombe"]
        )
        profils.verify_provider(db, account_id)
        db.commit()

    def decline(_index):
        for _ in range(5):
            with sessions() as db:
                profils.record_declined_alert(db, account_id)
                db.commit()

    _parallel(8, decline)

    with sessions() as db:
        provider = profils.provider_profile(db, account_id)
        assert (provider.consecutive_ignored, provider.status) == (40, "paused")


def test_one_alert_declined_simultaneously_counts_once(sessions):
    from backend.app import crud, ledger, profils

    with sessions() as db:
        account_id = ledger.account_id_for(db, ledger.TELEGRAM, 7, create=True)
        profils.register_provider(
            db, account_id, full_name="Jean", phone_number=None, services=["service_plomberie"], communes=["Gombe"]
        )
        profils.verify_provider(db, account_id)
        db.commit()
        mission, _ = crud.create_mission(
            db, channel=ledger.TELEGRAM, client_external_id="42", creation_key="k1", service="service_plomberie",
            commune="Gombe", destination_latitude=-4.3076,
            destination_longitude=15.3125, destination_landmark="Portail bleu après la poste",
        )
        mission_id = mission.mission_id

    def decline(_index):
        with sessions() as db:
            return crud.decline_alert(db, mission_id, account_id)[1]

    counted = _parallel(8, decline)

    assert sum(counted) == 1
    with sessions() as db:
        assert profils.provider_profile(db, account_id).consecutive_ignored == 1


def test_simultaneous_registrations_create_one_profile(sessions):
    from backend.app import ledger, profils

    def register(index):
        with sessions() as db:
            account_id = ledger.account_id_for(db, ledger.TELEGRAM, 7, create=True)
            _, created = profils.register_provider(
                db, account_id, full_name=f"Jean {index}", phone_number=None,
                services=["service_plomberie"], communes=["Gombe", "Lemba"],
            )
            db.commit()
            return account_id, created

    results = _parallel(8, register)

    assert len({account_id for account_id, _ in results}) == 1
    assert sum(created for _, created in results) == 1
    with sessions() as db:
        account_id = results[0][0]
        assert db.execute(text("SELECT COUNT(*) FROM provider_profiles")).scalar_one() == 1
        assert profils.provider_communes(db, account_id) == ["Gombe", "Lemba"]
        assert profils.provider_profile(db, account_id).status == "pending_verification"


def test_routes_of_the_bot_on_postgres(engine, monkeypatch):
    """Les routes du bot sur la base migrée : inscription au nom de l'acteur,
    validation par un admin, prestataires prévenus choisis par le backend,
    service hors catalogue refusé."""
    alembic("upgrade", "head")
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    from backend.app import admins

    with database.SessionLocal() as db:
        admins.grant(db, 999, "Admin de test")

    def actor(telegram_id):
        return {"X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}

    def alerted(key):
        mission = {
            "creation_key": key,
            "service": "service_plomberie",
            "commune": "Gombe",
            "destination": {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"},
        }
        return client.post("/api/bot/missions", json=mission, headers=actor(42)).json()["alerted_provider_telegram_ids"]

    try:
        with TestClient(main.app) as client:
            client.headers["X-API-Key"] = TELEGRAM_KEY
            body = {"full_name": "Jean", "phone_number": "+243810000007", "services": ["service_plomberie"], "communes": ["Gombe"]}
            registered = client.put("/api/me/provider-profile", json=body, headers=actor(7)).json()
            assert registered["provider"]["status"] == "pending_verification"
            refused = client.patch("/api/me/provider-profile/status", json={"status": "available"}, headers=actor(7))
            assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "provider_not_verified")
            assert alerted("k1") == []

            verified = client.post(f"/api/admin/providers/{registered['account_id']}/verify", headers=actor(999))
            assert verified.json()["provider"]["status"] == "available"
            assert alerted("k2") == [7]
            unknown = client.put("/api/me/provider-profile", json={**body, "services": ["service_peinture"]}, headers=actor(7))
            assert (unknown.status_code, unknown.json()["detail"]["code"]) == (400, "unknown_service")
    finally:
        database.engine.dispose()
