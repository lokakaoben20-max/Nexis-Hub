import importlib
import itertools
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

def acc(db, telegram_id):
    """Compte Nexis d'une personne connue par Telegram (créé au besoin)."""
    from backend.app import ledger

    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)



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


def _new_mission(db, crud, client_id, alert=()):
    """Mission créée par le backend (il lui donne son numéro)."""
    from backend.app import ledger

    mission, _ = crud.create_mission(
        db, channel=ledger.TELEGRAM, client_external_id=str(client_id), creation_key=f"demande-{next(_KEYS)}",
        service="service_menage", commune="Gombe", alert_provider_telegram_ids=list(alert),
        destination_latitude=-4.3076, destination_longitude=15.3125, destination_landmark="Portail bleu après la poste",
    )
    return mission


_KEYS = itertools.count(1)


def _seed_mission_with_quote(db, crud, models, mission_id, quote_created_at, provider_id=7, client_id=1):
    if db.get(models.BotUser, client_id) is None:
        db.add(models.BotUser(telegram_id=client_id))
    if db.get(models.BotProvider, provider_id) is None:
        db.add(models.BotProvider(telegram_id=provider_id, full_name="Prestataire Test"))
    db.commit()

    mission = _new_mission(db, crud, client_id, alert=(provider_id,))
    assert mission.mission_id == mission_id
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


def _paid_and_finished_mission(db, ledger, crud, mission_id, provider_id=7, client_id=1):
    assert _new_mission(db, crud, client_id, alert=(provider_id,)).mission_id == mission_id
    quote = crud.create_quote(db, mission_id, provider_id, amount=10.0, currency="USD", delay_hours=2)
    crud.accept_quote(db, quote.id, acc(db, client_id))
    ledger.fund_mission(db, mission_id, method="mobile_money", client_account_id=acc(db, client_id), quote_id=quote.id)
    ledger.start_mission(db, mission_id, acc(db, provider_id))
    ledger.finish_mission(db, mission_id, acc(db, provider_id))


def test_release_auto_confirmed_missions_only_after_24h(monkeypatch, tmp_path):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, tmp_path)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)))

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()

        _paid_and_finished_mission(db, ledger, crud, 1)
        db.get(models.BotMission, 1).status_changed_at = datetime.utcnow() - timedelta(hours=25)

        _paid_and_finished_mission(db, ledger, crud, 2)
        # status_changed_at reste "maintenant" pour la mission 2
        db.commit()

    released = tasks_module.release_auto_confirmed_missions()
    assert released == 1

    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).status == "completed"
        assert db.get(models.BotMission, 2).status == "awaiting_confirmation"
        assert ledger.wallet_balances(db, acc(db, 7))["USD"] == ledger.to_money("9.00")

    # Une notification au client et une au prestataire, pour la seule mission libérée.
    assert len(sent) == 2


def test_auto_release_never_pays_a_disputed_mission(monkeypatch, tmp_path):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, tmp_path)
    from backend.app import crud, ledger
    from backend.app import models

    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: None)

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()
        _paid_and_finished_mission(db, ledger, crud, 1)
        ledger.open_dispute(db, 1, acc(db, 1), "Travail bâclé")
        db.get(models.BotMission, 1).status_changed_at = datetime.utcnow() - timedelta(hours=72)
        db.commit()

    assert tasks_module.release_auto_confirmed_missions() == 0

    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).status == "disputed"
        assert ledger.wallet_balances(db, acc(db, 7))["USD"] == ledger.to_money(0)
        assert ledger.balance(db, ledger.ESCROW, 1, "USD") == ledger.to_money("10.00")


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

        from backend.app import crud

        # Deux prestataires couvrent ce service : seul le prévenu (7) est relancé.
        db.add(models.BotProvider(telegram_id=8, full_name="Non prévenu", services=["service_menage"], communes=["Gombe"]))
        db.commit()
        mission = _new_mission(db, crud, 1, alert=(7,))
        mission.created_at = datetime.utcnow() - timedelta(minutes=12)
        db.commit()

    first_run = tasks_module.send_provider_reminders()
    assert first_run == 1  # un seul prestataire matché, palier 10 min uniquement

    second_run = tasks_module.send_provider_reminders()
    assert second_run == 0  # déjà relancé pour ce palier, pas de doublon

    assert len(sent) == 1
    assert sent[0][0] == 7
