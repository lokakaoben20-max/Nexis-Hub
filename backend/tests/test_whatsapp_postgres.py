"""Canal WhatsApp, étape 1, sur un vrai Postgres : migration 1b2c3d4e5f6a et
inscriptions simultanées.

Même garde-fou que test_app_devices_migration.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import importlib
import os
import threading
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[2]
URL = os.getenv("NEXIS_TEST_POSTGRES_URL", "")
REVISION = "1b2c3d4e5f6a"
PREVIOUS = "b7c8d9e0f1a2"
TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-0001"
WHATSAPP_KEY = "test-whatsapp-service-key-not-a-secret-0002"

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


@pytest.fixture
def engine(monkeypatch):
    url = make_url(URL)
    if url.get_backend_name() != "postgresql" or not (url.database or "").endswith("_test"):
        pytest.fail("NEXIS_TEST_POSTGRES_URL doit viser une base Postgres jetable dont le nom finit par _test")
    monkeypatch.setenv("DATABASE_URL", URL)
    engine = create_engine(URL, future=True)
    with engine.begin() as connection:
        connection.execute(text("DROP SCHEMA public CASCADE"))
        connection.execute(text("CREATE SCHEMA public"))
    yield engine
    engine.dispose()


def alembic(command_name, revision):
    from alembic import command
    from alembic.config import Config

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    getattr(command, command_name)(config, revision)


def external_id_length(engine):
    column = next(c for c in inspect(engine).get_columns("channel_identities") if c["name"] == "external_id")
    return column["type"].length


def account_columns(engine):
    return {c["name"] for c in inspect(engine).get_columns("accounts")}


def test_upgrade_downgrade_and_upgrade_again(engine):
    alembic("upgrade", "head")
    assert external_id_length(engine) == 160
    assert "display_name" in account_columns(engine)

    alembic("downgrade", PREVIOUS)
    assert external_id_length(engine) == 64
    assert "display_name" not in account_columns(engine)

    alembic("upgrade", REVISION)
    assert external_id_length(engine) == 160


def test_upgrade_keeps_existing_telegram_identities(engine):
    alembic("upgrade", PREVIOUS)
    with engine.begin() as connection:
        account_id = connection.execute(
            text("INSERT INTO accounts (created_at, roles, language) VALUES (now(), '[\"client\"]', 'fr') RETURNING id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at) "
                "VALUES (:account_id, 'telegram', '42', now(), now())"
            ),
            {"account_id": account_id},
        )

    alembic("upgrade", REVISION)

    with engine.connect() as connection:
        rows = connection.execute(text("SELECT account_id, channel, external_id FROM channel_identities")).all()
        assert [tuple(row) for row in rows] == [(account_id, "telegram", "42")]


def test_downgrade_refuses_to_truncate_a_whatsapp_identity(engine):
    alembic("upgrade", REVISION)
    with engine.begin() as connection:
        account_id = connection.execute(
            text("INSERT INTO accounts (created_at, roles, language) VALUES (now(), '[\"client\"]', 'fr') RETURNING id")
        ).scalar_one()
        connection.execute(
            text(
                "INSERT INTO channel_identities (account_id, channel, external_id, verified_at, created_at) "
                "VALUES (:account_id, 'whatsapp', :bsuid, now(), now())"
            ),
            {"account_id": account_id, "bsuid": "CD." + "7" * 100},
        )

    with pytest.raises(RuntimeError, match="retour arrière refusé"):
        alembic("downgrade", PREVIOUS)
    assert external_id_length(engine) == 160


@pytest.fixture
def backend(engine, monkeypatch):
    alembic("upgrade", "head")
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    main.database = database
    yield main
    database.engine.dispose()


def _parallel(count, call):
    barrier = threading.Barrier(count)
    results = [None] * count

    def run(index):
        barrier.wait()
        results[index] = call(index)

    threads = [threading.Thread(target=run, args=(index,)) for index in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return results


def _register(app, bsuid, phone, key=None, with_headers=False):
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/whatsapp/client",
            json={"display_name": "Mado", "language": "ln", "phone": phone},
            headers={
                "X-API-Key": WHATSAPP_KEY,
                "X-Actor-Channel": "whatsapp",
                "X-Actor-Id": bsuid,
                "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}",
            },
        )
        if with_headers:
            return response.status_code, response.json(), response.headers.get("Idempotent-Replayed")
        return response.status_code, response.json()


def test_the_same_webhook_received_ten_times_in_parallel_acts_once(backend, engine):
    key = f"wamid.{uuid.uuid4().hex}"
    results = _parallel(
        10, lambda _index: _register(backend.app, "CD.555666777", "+243810000005", key=key, with_headers=True)
    )

    assert {status for status, _body, _replayed in results} == {200}
    # Une seule exécution, neuf réponses rejouées, toutes identiques.
    assert sorted(replayed or "false" for _status, _body, replayed in results) == ["false"] + ["true"] * 9
    assert len({repr(body) for _status, body, _replayed in results}) == 1
    assert results[0][1]["created"] is True
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM idempotency_keys")).scalar_one() == 1


def test_the_same_first_message_received_in_parallel_creates_one_account(backend, engine):
    # Messages différents (clés différentes) de la même personne au même instant.
    results = _parallel(8, lambda _index: _register(backend.app, "CD.111222333", "+243810000001"))

    assert {status for status, _body in results} == {200}
    assert len({body["account"]["account_id"] for _status, body in results}) == 1
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM accounts")).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM channel_identities")).scalar_one() == 1


def test_two_identities_racing_for_the_same_phone_never_share_it(backend, engine):
    results = _parallel(
        6, lambda index: _register(backend.app, f"CD.{index + 1}00200300", "+243810000002")
    )

    statuses = sorted(status for status, _body in results)
    assert statuses.count(200) == 1
    for status, body in results:
        if status != 200:
            assert (status, body["detail"]["code"]) == (409, "phone_owned_by_account")
    with engine.connect() as connection:
        holders = connection.execute(
            text("SELECT COUNT(*) FROM accounts WHERE phone_e164 = '+243810000002' AND phone_verified_at IS NOT NULL")
        ).scalar_one()
        assert holders == 1
        # Aucun compte orphelin : chaque compte créé a son identité.
        orphans = connection.execute(
            text("SELECT COUNT(*) FROM accounts a WHERE NOT EXISTS (SELECT 1 FROM channel_identities c WHERE c.account_id = a.id)")
        ).scalar_one()
        assert orphans == 0
        # Chaque refus est au journal d'audit, rattaché au compte qui a le numéro.
        events = connection.execute(
            text(
                "SELECT e.account_id FROM auth_events e WHERE e.type = 'whatsapp_phone_conflict'"
            )
        ).scalars().all()
        holder_id = connection.execute(
            text("SELECT id FROM accounts WHERE phone_e164 = '+243810000002'")
        ).scalar_one()
        assert events == [holder_id] * 5
