"""Admins de Nexis Hub enregistrés en base (backend.app.admins).

Plusieurs personnes peuvent être admin ; le rôle ne se donne et ne se retire
que par la commande, avec une raison, et n'est jamais effacé. Le backend le
revérifie à chaque décision : le bot n'a aucune liste locale."""

import importlib
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

TELEGRAM_KEY = "test-telegram-service-key-not-a-secret-001"
WHATSAPP_KEY = "test-whatsapp-service-key-not-a-secret-0002"
ADMIN = 900
OTHER_ADMIN = 901
STRANGER = 555


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
    return main


@pytest.fixture
def db(backend):
    with backend.database.SessionLocal() as session:
        yield session


def as_telegram(telegram_id):
    return {"X-API-Key": TELEGRAM_KEY, "X-Actor-Channel": "telegram", "X-Actor-Id": str(telegram_id)}


def _roles(db):
    from backend.app.models import AdminRole

    return db.query(AdminRole).order_by(AdminRole.id).all()


def test_granting_twice_keeps_one_role_and_revoking_keeps_the_trace(db):
    from backend.app import admins

    first = admins.grant(db, ADMIN, "Équipe litiges", now=datetime(2026, 11, 13, 9, 0))
    again = admins.grant(db, str(ADMIN), "Doublon", now=datetime(2026, 11, 13, 10, 0))
    assert again.id == first.id and len(_roles(db)) == 1
    assert admins.is_admin_telegram(db, ADMIN)

    admins.revoke(db, ADMIN, "Départ", now=datetime(2026, 11, 14, 9, 0))
    assert not admins.is_admin_telegram(db, ADMIN)
    assert admins.admin_telegram_ids(db) == []

    admins.grant(db, ADMIN, "Retour")
    roles = _roles(db)
    assert len(roles) == 2, "le retrait reste dans l'historique"
    assert (roles[0].granted_reason, roles[0].revoked_reason) == ("Équipe litiges", "Départ")
    assert roles[1].revoked_at is None
    assert admins.is_admin_telegram(db, ADMIN)


def test_several_admins_are_listed_in_the_order_they_were_named(db):
    from backend.app import admins

    admins.grant(db, OTHER_ADMIN, "Deuxième", now=datetime(2026, 11, 13, 10, 0))
    admins.grant(db, ADMIN, "Premier", now=datetime(2026, 11, 13, 9, 0))
    admins.grant(db, STRANGER, "Temporaire")
    admins.revoke(db, STRANGER, "Fin")

    assert admins.admin_telegram_ids(db) == [ADMIN, OTHER_ADMIN]
    assert not admins.is_admin_telegram(db, STRANGER)
    assert not admins.is_admin_telegram(db, 123456), "inconnu : pas de compte, pas admin"


@pytest.mark.parametrize(
    "telegram_id, reason",
    [(ADMIN, ""), (ADMIN, "   "), (ADMIN, "x" * 501), ("abc", "Raison"), (0, "Raison"), (-5, "Raison")],
)
def test_a_role_needs_a_reason_and_a_numeric_telegram_id(db, telegram_id, reason):
    from backend.app import admins

    with pytest.raises(admins.AdminError):
        admins.grant(db, telegram_id, reason)
    assert _roles(db) == []


def test_revoking_someone_who_is_not_admin_is_refused(db):
    from backend.app import admins

    with pytest.raises(admins.AdminError, match="n'est pas admin"):
        admins.revoke(db, STRANGER, "Erreur")


def test_the_database_refuses_two_active_roles_for_one_account(db):
    """Garde-fou en base, en plus du contrôle de `grant` : deux commandes
    simultanées ne créent jamais deux rôles actifs."""
    from backend.app import admins, ledger
    from backend.app.models import AdminRole

    role = admins.grant(db, ADMIN, "Premier")
    db.add(AdminRole(account_id=role.account_id, granted_at=datetime(2026, 11, 13), granted_reason="Doublon"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    assert len(_roles(db)) == 1
    assert ledger.account_id_for(db, ledger.TELEGRAM, ADMIN) == role.account_id


def test_the_command_names_lists_and_removes_admins(backend, capsys):
    from backend.app import admins

    assert admins.main(["liste"]) == 0
    assert "Aucun admin" in capsys.readouterr().out

    assert admins.main(["ajouter", str(ADMIN), "--raison", "Équipe litiges"]) == 0
    assert admins.main(["liste"]) == 0
    out = capsys.readouterr().out
    assert str(ADMIN) in out and "Un seul admin" in out

    assert admins.main(["ajouter", str(OTHER_ADMIN), "--raison", "Révisions"]) == 0
    capsys.readouterr()
    assert admins.main(["liste"]) == 0
    assert capsys.readouterr().out.split() == [str(ADMIN), str(OTHER_ADMIN)]

    assert admins.main(["retirer", str(ADMIN), "--raison", "Départ"]) == 0
    assert admins.main(["retirer", str(ADMIN), "--raison", "Encore"]) == 1
    assert "n'est pas admin" in capsys.readouterr().err
    assert admins.main(["ajouter", "abc", "--raison", "X"]) == 1


def test_the_bot_asks_the_backend_who_is_admin(backend, db):
    from backend.app import admins

    admins.grant(db, ADMIN, "Équipe litiges")
    with TestClient(backend.app) as client:
        assert client.get("/api/bot/admin/me", headers=as_telegram(ADMIN)).json()["admin"] is True
        assert client.get("/api/bot/admin/me", headers=as_telegram(STRANGER)).json()["admin"] is False
        listed = client.get("/api/bot/admins", headers={"X-API-Key": TELEGRAM_KEY})
        assert listed.json()["admins"] == [ADMIN]


def test_whatsapp_never_reads_or_acts_as_admin(backend, db):
    from backend.app import admins

    admins.grant(db, ADMIN, "Équipe litiges")
    whatsapp = {"X-API-Key": WHATSAPP_KEY, "X-Actor-Channel": "whatsapp", "X-Actor-Id": "CD.1234567890"}
    with TestClient(backend.app) as client:
        for path in ("/api/bot/admin/me", "/api/bot/admins", "/api/admin/stats"):
            response = client.get(path, headers=whatsapp)
            assert response.status_code == 403, path
            assert response.json()["detail"]["code"] == "channel_forbidden"


def test_the_backend_rechecks_the_role_on_every_admin_action(backend, db):
    from backend.app import admins

    with TestClient(backend.app) as client:
        refused = client.get("/api/admin/stats", headers=as_telegram(ADMIN))
        assert refused.status_code == 403 and refused.json()["detail"] == {"code": "not_admin"}

        admins.grant(db, ADMIN, "Équipe litiges")
        assert client.get("/api/admin/stats", headers=as_telegram(ADMIN)).status_code == 200

        admins.revoke(db, ADMIN, "Départ")
        assert client.get("/api/admin/stats", headers=as_telegram(ADMIN)).status_code == 403
