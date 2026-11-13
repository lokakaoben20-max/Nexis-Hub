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
# coup, ce qui exécute deux fois les classes de backend/app/models.py contre
# la même métadonnée et lève "Table ... is already defined".
from backend.app import database as _database_module  # noqa: F401
from backend.app import models as _models_module  # noqa: F401
from backend.app import tasks as _tasks_module  # noqa: F401
from backend.tests import profils_de_test  # noqa: E402

# Clé factice, jamais la vraie BACKEND_API_KEY_TELEGRAM de .env — même convention que
# backend/tests/test_main.py.
TEST_API_KEY = "test-backend-api-key-not-a-secret"

def acc(db, telegram_id):
    """Compte Nexis d'une personne connue par Telegram (créé au besoin)."""
    from backend.app import ledger

    return ledger.account_id_for(db, ledger.TELEGRAM, telegram_id, create=True)



def _reload_backend_with_db(monkeypatch, backend_db_url):
    """Recharge database/models/tasks contre une base jetable par test (SQLite, ou Postgres en CI).

    `tasks` doit être rechargé explicitement (contrairement à `crud`, qui
    reçoit sa session en paramètre) : ses tâches ouvrent leur propre session
    via `SessionLocal` importé au niveau module — sans ce rechargement, elles
    resteraient connectées au moteur de la base par défaut.
    """
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("BACKEND_API_KEY_TELEGRAM", TEST_API_KEY)
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
    from backend.tests import profils_de_test

    if profils_de_test.client_of(db, client_id) is None:
        profils_de_test.client(db, client_id)
    if profils_de_test.provider_of(db, provider_id) is None:
        profils_de_test.provider(db, provider_id, "Prestataire Test")

    mission = _new_mission(db, crud, client_id, alert=(provider_id,))
    assert mission.mission_id == mission_id
    quote = crud.create_quote(db, mission_id, provider_id, amount=10.0, currency="USD", delay_hours=2)
    quote.created_at = quote_created_at
    db.commit()
    return mission, quote


def test_expire_stale_quotes_expires_only_quotes_older_than_24h(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
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


def test_release_auto_confirmed_missions_only_after_their_deadline(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)))

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")

        _paid_and_finished_mission(db, ledger, crud, 1)
        # Terminée il y a 48 h et 1 minute : échéance passée.
        db.get(models.BotMission, 1).release_after = datetime.utcnow() - timedelta(minutes=1)

        _paid_and_finished_mission(db, ledger, crud, 2)
        # Terminée il y a 25 h : versée sous l'ancienne règle de 24 h, plus maintenant.
        mission_2 = db.get(models.BotMission, 2)
        mission_2.status_changed_at = datetime.utcnow() - timedelta(hours=25)
        mission_2.release_after = mission_2.status_changed_at + timedelta(hours=48)
        db.commit()

    released = tasks_module.release_auto_confirmed_missions()
    assert released == 1

    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).status == "completed"
        assert db.get(models.BotMission, 2).status == "awaiting_confirmation"
        assert ledger.wallet_balances(db, acc(db, 7))["USD"] == ledger.to_money("9.00")

    # Une notification au client et une au prestataire, pour la seule mission libérée.
    assert len(sent) == 2


def test_auto_release_never_pays_a_disputed_mission(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: None)

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")
        _paid_and_finished_mission(db, ledger, crud, 1)
        ledger.open_dispute(db, 1, acc(db, 1), "Travail bâclé")
        mission = db.get(models.BotMission, 1)
        mission.status_changed_at = datetime.utcnow() - timedelta(hours=72)
        mission.release_after = datetime.utcnow() - timedelta(hours=24)
        db.commit()

    assert tasks_module.release_auto_confirmed_missions() == 0

    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).status == "disputed"
        assert ledger.wallet_balances(db, acc(db, 7))["USD"] == ledger.to_money(0)
        assert ledger.balance(db, ledger.ESCROW, 1, "USD") == ledger.to_money("10.00")


def _overdue_dispute(db, ledger, crud, models, mission_id, hours_late):
    _paid_and_finished_mission(db, ledger, crud, mission_id)
    ledger.open_dispute(db, mission_id, acc(db, 1), "Travail bâclé")
    mission = db.get(models.BotMission, mission_id)
    mission.dispute_opened_at = datetime.utcnow() - timedelta(hours=48 + hours_late)
    mission.dispute_deadline = datetime.utcnow() - timedelta(hours=hours_late)
    db.commit()


def test_overdue_dispute_alerts_the_admin_once_then_daily_without_moving_money(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "ADMIN_TELEGRAM_ID", "900")
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)) or True)

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()
        _overdue_dispute(db, ledger, crud, models, 1, hours_late=3)
        # Litige encore dans le délai de réponse : pas d'alerte.
        _paid_and_finished_mission(db, ledger, crud, 2)
        ledger.open_dispute(db, 2, acc(db, 1), "Pas venu")

    now = datetime.utcnow()
    assert tasks_module.alert_overdue_disputes(now) == 1
    assert [telegram_id for telegram_id, _ in sent] == [900]
    assert "NXH-0001" in sent[0][1]

    # Même heure, puis 23 h plus tard : pas de relance.
    assert tasks_module.alert_overdue_disputes(now) == 0
    assert tasks_module.alert_overdue_disputes(now + timedelta(hours=23)) == 0
    # 24 h après la première alerte : une relance.
    assert tasks_module.alert_overdue_disputes(now + timedelta(hours=24)) == 1
    assert len(sent) == 2

    with database_module.SessionLocal() as db:
        mission = db.get(models.BotMission, 1)
        assert (mission.status, mission.payment_status) == ("disputed", "paid_escrow")
        assert ledger.balance(db, ledger.ESCROW, 1, "USD") == ledger.to_money("10.00")
        assert ledger.wallet_balances(db, acc(db, 7))["USD"] == ledger.to_money(0)


def test_overdue_dispute_alert_is_retried_when_telegram_refuses_it(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    accepted = []
    monkeypatch.setattr(tasks_module, "ADMIN_TELEGRAM_ID", "900")
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: bool(accepted))

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()
        _overdue_dispute(db, ledger, crud, models, 1, hours_late=1)

    assert tasks_module.alert_overdue_disputes() == 0
    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).dispute_overdue_alerted_at is None

    accepted.append(True)
    assert tasks_module.alert_overdue_disputes() == 1


def test_overdue_dispute_is_not_marked_alerted_without_an_admin(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "ADMIN_TELEGRAM_ID", None)
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append(telegram_id) or True)

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()
        _overdue_dispute(db, ledger, crud, models, 1, hours_late=1)

    assert tasks_module.alert_overdue_disputes() == 0
    assert sent == []
    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).dispute_overdue_alerted_at is None


def test_a_settled_dispute_is_never_reported_late(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "ADMIN_TELEGRAM_ID", "900")
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append(telegram_id) or True)

    with database_module.SessionLocal() as db:
        db.add(models.BotUser(telegram_id=1))
        db.add(models.BotProvider(telegram_id=7, full_name="Prestataire Test"))
        db.commit()
        _overdue_dispute(db, ledger, crud, models, 1, hours_late=5)
        ledger.resolve_dispute(db, 1, decision="refund", admin_telegram_id=900)

    assert tasks_module.alert_overdue_disputes() == 0
    assert sent == []


def test_send_provider_reminders_does_not_duplicate_within_same_tier(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)))

    with database_module.SessionLocal() as db:
        profils_de_test.provider(db, 7, "Prestataire Test")
        profils_de_test.client(db, 1)

        from backend.app import crud

        # Deux prestataires couvrent ce service : seul le prévenu (7) est relancé.
        profils_de_test.provider(db, 8, "Non prévenu")
        mission = _new_mission(db, crud, 1, alert=(7,))
        mission.created_at = datetime.utcnow() - timedelta(minutes=12)
        db.commit()

    first_run = tasks_module.send_provider_reminders()
    assert first_run == 1  # un seul prestataire matché, palier 10 min uniquement

    second_run = tasks_module.send_provider_reminders()
    assert second_run == 0  # déjà relancé pour ce palier, pas de doublon

    assert len(sent) == 1
    assert sent[0][0] == 7
