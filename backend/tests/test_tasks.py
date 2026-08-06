import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Pré-importe une fois au chargement du module (comme `from backend.app.main
# import app` dans test_main.py) : sans ça, le premier appel à
# `_reload_backend_with_db` importe puis recharge le même module coup sur
# coup, ce qui exécute deux fois les `class BotUser(Base): ...` de
# backend/app/models.py contre la même métadonnée et lève "Table 'bot_users'
# is already defined".
from backend.app import database as _database_module  # noqa: F401
from backend.app import models as _models_module  # noqa: F401
from backend.app import tasks as _tasks_module  # noqa: F401

# Clé factice, jamais la vraie BACKEND_API_KEY de .env — même convention que
# backend/tests/test_main.py.
TEST_API_KEY = "test-backend-api-key-not-a-secret"


def _reload_backend_with_db(monkeypatch, tmp_path, name="test_tasks.db"):
    """Recharge database/models/tasks contre une SQLite jetable par test.

    `tasks` doit être rechargé explicitement (contrairement à `crud`, qui
    reçoit sa session en paramètre) : ses tâches ouvrent leur propre session
    via `SessionLocal` importé au niveau module — sans ce rechargement, elles
    resteraient connectées au moteur de la base par défaut.
    """
    db_path = tmp_path / name
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BACKEND_API_KEY", TEST_API_KEY)
    monkeypatch.setenv("ADMIN_TELEGRAM_ID", "999")

    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    tasks_module = importlib.reload(importlib.import_module("backend.app.tasks"))
    database_module.init_db()
    return database_module, tasks_module


def _seed_mission_with_quote(db, crud, models, mission_id, quote_created_at, provider_id=7, client_id=1):
    if db.get(models.BotUser, client_id) is None:
        db.add(models.BotUser(telegram_id=client_id))
    if db.get(models.BotProvider, provider_id) is None:
        db.add(models.BotProvider(telegram_id=provider_id, full_name="Prestataire Test"))
    db.commit()

    mission = crud.create_mission(db, client_id, mission_id, "service_menage", "Gombe")
    quote = crud.create_quote(db, mission_id, provider_id, amount=10.0, currency="USD", delay_hours=2)
    quote.created_at = quote_created_at
    db.commit()
    return mission, quote


def test_expire_stale_quotes_expires_only_quotes_older_than_24h(monkeypatch, tmp_path):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, tmp_path)
    from backend.app import crud
    from backend.app import models

    with database_module.SessionLocal() as db:
        _seed_mission_with_quote(db, crud, models, 1, datetime.utcnow() - timedelta(hours=25))
        _seed_mission_with_quote(db, crud, models, 2, datetime.utcnow() - timedelta(hours=23))

        expired = crud.expire_stale_quotes(db)
        assert len(expired) == 1

        db.expire_all()
        mission_1 = db.get(models.BotMission, 1)
        mission_2 = db.get(models.BotMission, 2)
        assert mission_1.status == "pending"  # plus aucun devis vivant -> redevient matchable
        assert mission_2.status == "quoted"

        quotes_by_mission = {q.mission_id: q.status for q in db.query(models.BotQuote).all()}
        assert quotes_by_mission[1] == "expired"
        assert quotes_by_mission[2] == "pending"


def test_release_auto_confirmed_missions_only_after_24h(monkeypatch, tmp_path):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, tmp_path)
    from backend.app import crud
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)))

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()

        mission_old = crud.create_mission(db, 1, 1, "service_menage", "Gombe")
        quote_old = crud.create_quote(db, 1, 7, amount=10.0, currency="USD", delay_hours=2)
        crud.accept_quote(db, quote_old.id)
        crud.mark_quote_paid(db, quote_old.id)
        crud.start_mission(db, 1, 7)
        crud.finish_mission(db, 1, 7)
        db.get(models.BotMission, 1).status_changed_at = datetime.utcnow() - timedelta(hours=25)

        mission_recent = crud.create_mission(db, 1, 2, "service_menage", "Gombe")
        quote_recent = crud.create_quote(db, 2, 7, amount=10.0, currency="USD", delay_hours=2)
        crud.accept_quote(db, quote_recent.id)
        crud.mark_quote_paid(db, quote_recent.id)
        crud.start_mission(db, 2, 7)
        crud.finish_mission(db, 2, 7)
        # status_changed_at reste "maintenant" pour la mission 2

        db.commit()

    released = tasks_module.release_auto_confirmed_missions()
    assert released == 1

    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).status == "completed"
        assert db.get(models.BotMission, 2).status == "awaiting_confirmation"
        provider = db.get(models.BotProvider, 7)
        assert provider.wallet_balance_usd > 0

    # Une notification au client et une au prestataire, pour la seule mission libérée.
    assert len(sent) == 2


def test_send_provider_reminders_does_not_duplicate_within_same_tier(monkeypatch, tmp_path):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, tmp_path)
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)))

    with database_module.SessionLocal() as db:
        db.add(models.BotProvider(
            telegram_id=7,
            full_name="Prestataire Test",
            services=["service_menage"],
            communes=["Gombe"],
        ))
        db.add(models.BotUser(telegram_id=1))
        db.commit()

        mission = models.BotMission(
            mission_id=1,
            telegram_id=1,
            service="service_menage",
            commune="Gombe",
            status="pending",
        )
        db.add(mission)
        db.commit()
        mission.created_at = datetime.utcnow() - timedelta(minutes=12)
        db.commit()

    first_run = tasks_module.send_provider_reminders()
    assert first_run == 1  # un seul prestataire matché, palier 10 min uniquement

    second_run = tasks_module.send_provider_reminders()
    assert second_run == 0  # déjà relancé pour ce palier, pas de doublon

    assert len(sent) == 1
