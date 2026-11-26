"""Missions WhatsApp (étape 5) sur un vrai Postgres : migration c1d2e3f4a5b6
et double appui simultané sur « Confirmer ».

Même garde-fou que test_whatsapp_postgres.py : ne s'exécute que si
`NEXIS_TEST_POSTGRES_URL` désigne une base Postgres jetable dont le nom finit
par `_test` (son schéma `public` est entièrement effacé).
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.tests.test_whatsapp_postgres import URL, WHATSAPP_KEY, _parallel, alembic, backend, engine  # noqa: F401

REVISION = "c1d2e3f4a5b6"
PREVIOUS = "b0c1d2e3f4a5"
BSUID = "CD.424242424242"

pytestmark = pytest.mark.skipif(not URL, reason="NEXIS_TEST_POSTGRES_URL absent : pas de Postgres de test")


def _headers(key=None):
    return {
        "X-API-Key": WHATSAPP_KEY,
        "X-Actor-Channel": "whatsapp",
        "X-Actor-Id": BSUID,
        "Idempotency-Key": key or f"wamid.{uuid.uuid4().hex}",
    }


def _mission_request():
    return {
        "creation_key": "demande-whatsapp-1",
        "service": "service_nettoyage",
        "commune": "Gombe",
        "description": "Nettoyer le salon",
        "destination": {"latitude": -4.3076, "longitude": 15.3125, "landmark": "Portail bleu après la poste"},
    }


def _register(app):
    with TestClient(app) as test_client:
        response = test_client.post(
            "/api/whatsapp/client", json={"display_name": "Mado", "language": "fr"}, headers=_headers()
        )
        assert response.status_code == 200, response.json()


def _create(app):
    with TestClient(app) as test_client:
        response = test_client.post("/api/bot/missions", json=_mission_request(), headers=_headers())
        return response.status_code, response.json()


def test_two_taps_on_confirm_at_the_same_instant_create_one_mission(backend, engine):  # noqa: F811
    _register(backend.app)
    results = _parallel(6, lambda _index: _create(backend.app))

    assert {status for status, _body in results} == {200}
    assert len({body["mission"]["mission_id"] for _status, body in results}) == 1
    assert sorted(body["created"] for _status, body in results) == [False] * 5 + [True]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM bot_missions")).scalar_one() == 1
        assert connection.execute(text("SELECT telegram_id FROM bot_missions")).scalar_one() is None


def test_a_mission_always_names_its_client(engine):  # noqa: F811
    alembic("upgrade", REVISION)
    with pytest.raises(IntegrityError, match="ck_bot_missions_client_known"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO bot_missions (service, commune, currency, description, urgent, commission_amount,"
                    " tola_fee, aggregator_fee, total_client, net_provider, created_at, status_changed_at,"
                    " reminder_sent_10min) VALUES ('service_nettoyage', 'Gombe', 'USD', '', false, 0, 0, 0, 0, 0,"
                    " now(), now(), false)"
                )
            )


def test_downgrade_refuses_to_drop_a_whatsapp_mission(backend, engine):  # noqa: F811
    _register(backend.app)
    assert _create(backend.app)[0] == 200
    backend.database.engine.dispose()

    with pytest.raises(RuntimeError, match="retour arrière impossible"):
        alembic("downgrade", PREVIOUS)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM bot_missions")).scalar_one() == 1


def test_upgrade_downgrade_and_upgrade_again_without_whatsapp_missions(engine):  # noqa: F811
    alembic("upgrade", REVISION)
    alembic("downgrade", PREVIOUS)
    with engine.connect() as connection:
        nullable = connection.execute(
            text("SELECT is_nullable FROM information_schema.columns WHERE table_name = 'bot_missions' AND column_name = 'telegram_id'")
        ).scalar_one()
    assert nullable == "NO"
    alembic("upgrade", REVISION)
