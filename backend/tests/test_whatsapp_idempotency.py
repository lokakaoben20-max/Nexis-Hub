"""Canal WhatsApp, étape 2 : un même message reçu plusieurs fois n'agit
qu'une fois (backend/app/idempotency.py). Les envois simultanés sont testés
sur un vrai Postgres dans test_whatsapp_postgres.py.
"""

import importlib
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from test_whatsapp_channel import (
    BSUID,
    OTHER_BSUID,
    TELEGRAM_KEY,
    WHATSAPP_KEY,
    api_routes,
    as_whatsapp,
)

# Clé générée à chaque exécution : jamais de faux identifiant figé dans le code.
KEY = f"wamid.{uuid.uuid4().hex}"


@pytest.fixture
def backend(tmp_path, monkeypatch):
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'idempotency.db'}")
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TELEGRAM_KEY)
    monkeypatch.setenv("BACKEND_API_KEY_WHATSAPP", WHATSAPP_KEY)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    main = importlib.reload(importlib.import_module("backend.app.main"))
    database.init_db()
    main.database = database
    return main


@pytest.fixture
def client(backend):
    with TestClient(backend.app) as test_client:
        yield test_client


def post(client, *, key=KEY, bsuid=BSUID, name="Mado", phone="+243810000001"):
    headers = as_whatsapp(bsuid)
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.post(
        "/api/whatsapp/client", json={"display_name": name, "language": "ln", "phone": phone}, headers=headers
    )


def counts(backend):
    from backend.app.models import IdempotencyKey, NexisAccount

    with backend.database.SessionLocal() as db:
        return db.query(NexisAccount).count(), db.query(IdempotencyKey).count()


# --- La clé est obligatoire et bien formée ---------------------------------------


def test_a_whatsapp_write_without_key_is_refused_and_does_nothing(client, backend):
    response = post(client, key=None)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "idempotency_key_required"
    assert counts(backend) == (0, 0)


@pytest.mark.parametrize("key", ["court", "wamid.avec espace", "wamid.a*b$c%d!", "w" * 201])
def test_a_malformed_key_is_refused(client, backend, key):
    response = post(client, key=key)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "invalid_idempotency_key"
    assert counts(backend) == (0, 0)


# --- Rejeu ----------------------------------------------------------------------------


def test_the_same_message_twice_acts_once_and_answers_the_same(client, backend):
    first = post(client)
    second = post(client)

    assert first.status_code == second.status_code == 200
    assert first.headers.get("Idempotent-Replayed") is None
    assert second.headers["Idempotent-Replayed"] == "true"
    assert second.json() == first.json()
    assert first.json()["created"] is True
    assert counts(backend) == (1, 1)


def test_a_new_message_after_the_first_is_a_new_action(client, backend):
    post(client)
    response = post(client, key=KEY + "2", name="Mado K.")
    assert response.headers.get("Idempotent-Replayed") is None
    assert response.json()["created"] is False
    assert response.json()["account"]["display_name"] == "Mado K."
    assert counts(backend) == (1, 2)


def test_the_same_key_with_another_body_is_refused_and_changes_nothing(client, backend):
    post(client)
    response = post(client, name="Quelqu'un d'autre")

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_key_reused"
    from backend.app.models import ClientProfile

    with backend.database.SessionLocal() as db:
        assert db.query(ClientProfile).one().first_name == "Mado"


def test_the_same_key_from_another_person_is_refused(client, backend):
    post(client)
    response = post(client, bsuid=OTHER_BSUID, phone="+243810000009")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "idempotency_key_reused"
    assert counts(backend) == (1, 1)


# --- Tout ou rien ---------------------------------------------------------------------


def test_a_refused_action_records_no_key_and_is_evaluated_again(client, backend):
    client.put(
        "/api/me/client-profile",
        json={"first_name": "Ben", "phone_number": "+243810000001", "phone_verified": True},
        headers={"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": "42"},
    )
    assert post(client).json()["detail"]["code"] == "phone_owned_by_account"
    assert counts(backend) == (1, 0)

    # Le même message rejoué est réévalué (aucune réponse n'était enregistrée).
    assert post(client).json()["detail"]["code"] == "phone_owned_by_account"


def test_a_failure_after_the_action_leaves_neither_the_action_nor_the_key(backend, monkeypatch):
    from backend.app import crud

    real = crud.register_whatsapp_client

    def register_then_fail(db, **kwargs):
        real(db, **kwargs)
        raise RuntimeError("panne simulée entre l'action et la validation")

    monkeypatch.setattr(crud, "register_whatsapp_client", register_then_fail)
    with TestClient(backend.app, raise_server_exceptions=False) as test_client:
        assert post(test_client).status_code == 500
    assert counts(backend) == (0, 0)

    # Au rejeu, le message agit normalement.
    monkeypatch.setattr(crud, "register_whatsapp_client", real)
    with TestClient(backend.app) as test_client:
        response = post(test_client)
    assert response.status_code == 200
    assert response.json()["created"] is True
    assert counts(backend) == (1, 1)


def test_a_failure_while_saving_the_key_cancels_the_action(backend, monkeypatch):
    from backend.app import idempotency

    def broken_key(**_kwargs):
        raise RuntimeError("panne simulée à l'écriture de la clé")

    monkeypatch.setattr(idempotency, "IdempotencyKey", broken_key)
    with TestClient(backend.app, raise_server_exceptions=False) as test_client:
        assert post(test_client).status_code == 500
    monkeypatch.undo()
    assert counts(backend) == (0, 0)


# --- Aucune écriture WhatsApp sans idempotence ------------------------------------------


def test_every_write_open_to_whatsapp_is_idempotent(backend):
    writes = [
        (method, path)
        for method, path, endpoint in api_routes(backend)
        if method in backend.WRITE_METHODS and "whatsapp" in backend.route_channels(endpoint)
    ]
    assert sorted(writes) == [("PATCH", "/api/me/language"), ("PATCH", "/api/me/name"), ("POST", "/api/whatsapp/client")]
    for method, path, endpoint in api_routes(backend):
        if (method, path) in writes:
            assert backend.is_idempotent(endpoint), (method, path)


def test_the_backend_refuses_to_start_with_a_whatsapp_write_without_idempotence(backend):
    @backend.router.post("/api/whatsapp/oubli")
    @backend.open_to("whatsapp")
    def oubli():
        return {}

    with pytest.raises(RuntimeError, match="sans @idempotent"):
        backend.check_route_policies()


# --- Profil : langue et prénom ------------------------------------------------------


def patch_me(client, path, body, *, key):
    headers = as_whatsapp(BSUID)
    if key is not None:
        headers["Idempotency-Key"] = key
    return client.patch(path, json=body, headers=headers)


@pytest.mark.parametrize(
    "path, body", [("/api/me/language", {"language": "fr"}), ("/api/me/name", {"first_name": "Mado K."})]
)
def test_profile_writes_from_whatsapp_need_a_key(client, backend, path, body):
    post(client)
    response = patch_me(client, path, body, key=None)
    assert response.status_code == 400
    assert response.json()["detail"]["code"] == "idempotency_key_required"


@pytest.mark.parametrize(
    "path, body", [("/api/me/language", {"language": "fr"}), ("/api/me/name", {"first_name": "Mado K."})]
)
def test_profile_writes_from_whatsapp_act_once(client, backend, path, body):
    post(client)
    key = f"wamid.{uuid.uuid4().hex}"
    first = patch_me(client, path, body, key=key)
    second = patch_me(client, path, body, key=key)
    assert first.status_code == second.status_code == 200
    assert second.headers["Idempotent-Replayed"] == "true"
    assert second.json() == first.json()
    assert counts(backend) == (1, 2)
    other = patch_me(client, path, {**body, **({"language": "en"} if "language" in body else {"first_name": "Autre"})}, key=key)
    assert other.status_code == 409


def test_a_refused_profile_write_records_no_key(client, backend):
    post(client)
    response = patch_me(client, "/api/me/language", {"language": "xx"}, key=f"wamid.{uuid.uuid4().hex}")
    assert response.status_code >= 400
    assert counts(backend) == (1, 1)


# --- Purge ------------------------------------------------------------------------------


def test_old_keys_are_purged_and_recent_ones_kept(backend):
    from backend.app import idempotency
    from backend.app.models import IdempotencyKey

    now = datetime(2026, 11, 12, 12, 0, 0)
    with backend.database.SessionLocal() as db:
        for key, age in (("wamid.vieille-cle-01", timedelta(days=31)), ("wamid.recente-cle-01", timedelta(days=29))):
            db.add(
                IdempotencyKey(
                    channel="whatsapp", key=key, fingerprint="0" * 64, response_status=200,
                    response_body={"status": "ok"}, created_at=now - age,
                )
            )
        db.commit()
        assert idempotency.purge(db, now=now) == 1
        assert [row.key for row in db.query(IdempotencyKey).all()] == ["wamid.recente-cle-01"]


def test_the_purge_runs_every_day():
    from backend.app import taches

    tache = taches.CALENDRIER["purge-cles-idempotence"]
    # Par nom : d'autres tests rechargent les modules.
    assert (tache.fonction.__module__, tache.fonction.__name__) == ("backend.app.tasks", "purge_idempotency_keys")
    assert tache.frequence.cron == "15 3 * * *"
