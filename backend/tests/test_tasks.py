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

    database_module = importlib.reload(importlib.import_module("backend.app.database"))
    importlib.reload(importlib.import_module("backend.app.models"))
    tasks_module = importlib.reload(importlib.import_module("backend.app.tasks"))
    database_module.init_db()
    return database_module, tasks_module


def _new_mission(db, crud, client_id, alert=()):
    """Mission créée par le backend (il lui donne son numéro)."""
    from backend.app import ledger

    from backend.tests import profils_de_test

    profils_de_test.alerted(db, alert)
    mission, _ = crud.create_mission(
        db, channel=ledger.TELEGRAM, client_external_id=str(client_id), creation_key=f"demande-{next(_KEYS)}",
        service="service_plomberie", commune="Gombe",
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


def test_every_admin_gets_the_alert_and_one_failed_send_does_not_hide_it(monkeypatch, tmp_path, backend_db_url):
    """Plusieurs admins : chacun est prévenu. Un envoi raté (bot bloqué par
    l'un) ne compte pas comme une alerte manquée tant qu'un autre l'a reçue ;
    un admin retiré n'est plus prévenu."""
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import admins, crud, ledger
    from backend.app import models

    attempts = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: attempts.append(telegram_id) or telegram_id != 900)

    with database_module.SessionLocal() as db:
        for telegram_id in (900, 901, 902):
            profils_de_test.admin(db, telegram_id)
        admins.revoke(db, 902, "Départ")
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")
        _overdue_dispute(db, ledger, crud, models, 1, hours_late=3)

    assert tasks_module.alert_overdue_disputes(datetime.utcnow()) == 1
    assert attempts == [900, 901]
    with database_module.SessionLocal() as db:
        assert db.get(models.BotMission, 1).dispute_overdue_alerted_at is not None


def test_overdue_dispute_alerts_the_admin_once_then_daily_without_moving_money(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    with database_module.SessionLocal() as db:
        profils_de_test.admin(db, 900)
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)) or True)

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")
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
    with database_module.SessionLocal() as db:
        profils_de_test.admin(db, 900)
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: bool(accepted))

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")
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
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append(telegram_id) or True)

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")
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
    with database_module.SessionLocal() as db:
        profils_de_test.admin(db, 900)
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append(telegram_id) or True)

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, "Prestataire Test")
        db.commit()
        _overdue_dispute(db, ledger, crud, models, 1, hours_late=5)
        admin_account = ledger.account_id_for(db, ledger.TELEGRAM, 900, create=True)
        ledger.decide_dispute(db, 1, decision="refund", admin_account_id=admin_account, admin_telegram_id=900)

    # Décision prise, pas encore exécutée : elle n'attend plus personne.
    assert tasks_module.alert_overdue_disputes() == 0

    with database_module.SessionLocal() as db:
        decision = ledger.dispute_decisions(db, 1)[0]
        ledger.execute_dispute_decision(db, decision.id, now=decision.execute_after)

    assert tasks_module.alert_overdue_disputes() == 0
    assert sent == []


def _decided_dispute(db, ledger, crud, models, decision="split", percentage=50):
    profils_de_test.client(db, 1)
    profils_de_test.provider(db, 7, full_name="Prestataire Test")
    _paid_and_finished_mission(db, ledger, crud, 1)
    ledger.open_dispute(db, 1, acc(db, 1), "Travail bâclé")
    ledger.decide_dispute(db, 1, decision=decision, admin_account_id=acc(db, 900), admin_telegram_id=900, provider_percentage=percentage)
    return ledger.dispute_decisions(db, 1)[0].execute_after


def test_due_dispute_decisions_are_executed_once_and_both_parties_told(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text, *_: sent.append((telegram_id, text)) or True)

    with database_module.SessionLocal() as db:
        execute_after = _decided_dispute(db, ledger, crud, models)

    assert tasks_module.execute_due_dispute_decisions(execute_after - timedelta(seconds=1)) == 0
    assert sent == []
    with database_module.SessionLocal() as db:
        assert ledger.balance(db, ledger.ESCROW, 1, "USD") == ledger.to_money("10.00")

    assert tasks_module.execute_due_dispute_decisions(execute_after) == 1
    assert tasks_module.execute_due_dispute_decisions(execute_after + timedelta(hours=1)) == 0

    # Total 10.00, commission 1.00, net 9.00 ; partage 50 % au prorata.
    with database_module.SessionLocal() as db:
        assert ledger.wallet_balances(db, acc(db, 7))["USD"] == ledger.to_money("4.50")
        assert ledger.balance(db, ledger.PLATFORM, None, "USD") == ledger.to_money("0.50")
        assert ledger.wallet_balances(db, acc(db, 1))["USD"] == ledger.to_money("5.00")
        assert db.get(models.BotMission, 1).payment_status == "split"
    assert sorted(telegram_id for telegram_id, _ in sent) == [1, 7]
    assert "5.00 USD" in dict(sent)[1]
    assert "4.50 USD" in dict(sent)[7]


def test_a_contested_decision_is_never_executed_and_is_reported_when_late(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    with database_module.SessionLocal() as db:
        profils_de_test.admin(db, 900)
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text, *_: sent.append((telegram_id, text)) or True)

    with database_module.SessionLocal() as db:
        execute_after = _decided_dispute(db, ledger, crud, models, decision="release", percentage=None)
        contested_at = execute_after - timedelta(hours=1)
        ledger.contest_dispute_decision(db, 1, acc(db, 1), "Le travail n'est pas fini", now=contested_at)

    assert tasks_module.execute_due_dispute_decisions(execute_after + timedelta(days=10)) == 0
    # Décision contestée : la révision a 48 h, puis l'admin est relancé.
    assert tasks_module.alert_overdue_disputes(contested_at + timedelta(hours=47)) == 0
    assert tasks_module.alert_overdue_disputes(contested_at + timedelta(hours=48)) == 1
    assert sent[-1][0] == 900
    assert "contestée" in sent[-1][1] and "autre personne" in sent[-1][1]
    with database_module.SessionLocal() as db:
        assert ledger.balance(db, ledger.ESCROW, 1, "USD") == ledger.to_money("10.00")
        assert ledger.mission_operation(db, 1, ledger.SETTLEMENT) is None


def test_decision_notice_gives_amounts_deadline_and_a_contest_button(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger
    from backend.app import models

    sent = []
    monkeypatch.setattr(
        tasks_module, "send_telegram_message", lambda telegram_id, text, markup=None: sent.append((telegram_id, text, markup)) or True
    )

    with database_module.SessionLocal() as db:
        execute_after = _decided_dispute(db, ledger, crud, models, percentage="30")
        tasks_module.notify_dispute_decided(db, db.get(models.BotMission, 1))

    by_person = {telegram_id: (text, markup) for telegram_id, text, markup in sent}
    assert set(by_person) == {1, 7}
    client_text, client_markup = by_person[1]
    provider_text, provider_markup = by_person[7]
    # Total 10.00 : prestataire 9.00 × 30 % = 2.70, commission 0.30, client 7.00.
    assert "Remboursé à vous : <b>7.00 USD</b>" in client_text
    assert "Versé au prestataire : <b>2.70 USD</b>" in client_text
    assert "Versé à vous : <b>2.70 USD</b>" in provider_text
    kinshasa = execute_after + timedelta(hours=1)
    assert f"{kinshasa:%d/%m/%Y %H:%M}" in client_text
    assert client_markup["inline_keyboard"][0][0]["callback_data"] == "dispute_contest_c_1"
    assert provider_markup["inline_keyboard"][0][0]["callback_data"] == "dispute_contest_p_1"


def test_amounts_in_francs_have_no_decimals():
    from backend.app import tasks
    from decimal import Decimal

    assert tasks._amount_text(Decimal("14000.00"), "CDF") == ("14 000", "FC")
    assert tasks._amount_text(Decimal("5"), "USD") == ("5.00", "USD")


def test_send_provider_reminders_does_not_duplicate_within_same_tier(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)

    sent = []
    monkeypatch.setattr(tasks_module, "send_telegram_message", lambda telegram_id, text: sent.append((telegram_id, text)))

    with database_module.SessionLocal() as db:
        profils_de_test.provider(db, 7, "Prestataire Test")
        profils_de_test.client(db, 1)

        from backend.app import crud

        # Un autre prestataire fait ce service ailleurs : il n'est pas prévenu,
        # donc jamais relancé ; seul le prévenu (7) l'est.
        profils_de_test.provider(db, 8, "Non prévenu", communes=("Lemba",))
        mission = _new_mission(db, crud, 1, alert=(7,))
        mission.created_at = datetime.utcnow() - timedelta(minutes=12)
        db.commit()

    first_run = tasks_module.send_provider_reminders()
    assert first_run == 1  # un seul prestataire matché, palier 10 min uniquement

    second_run = tasks_module.send_provider_reminders()
    assert second_run == 0  # déjà relancé pour ce palier, pas de doublon

    assert len(sent) == 1
    assert sent[0][0] == 7


def test_an_unanswered_agreement_expires_once_and_the_client_is_told(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger

    sent = []
    monkeypatch.setattr(
        tasks_module, "send_telegram_message", lambda telegram_id, text, markup=None: sent.append((telegram_id, text, markup)) or True
    )

    with database_module.SessionLocal() as db:
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, full_name="Prestataire Test")
        _paid_and_finished_mission(db, ledger, crud, 1)
        ledger.open_dispute(db, 1, acc(db, 1), "Travail bâclé")
        ledger.propose_dispute_settlement(db, 1, acc(db, 1), kind="refund")
        expires_at = ledger.settlement_offers(db, 1)[0].expires_at

    assert tasks_module.expire_settlement_offers(expires_at - timedelta(seconds=1)) == 0
    assert tasks_module.expire_settlement_offers(expires_at) == 1
    assert tasks_module.expire_settlement_offers(expires_at + timedelta(hours=1)) == 0

    assert [(telegram_id, "NXH-0001" in text) for telegram_id, text, _ in sent] == [(1, True)]
    # Le client peut faire une autre proposition depuis le message.
    assert sent[0][2]["inline_keyboard"][0][0]["callback_data"] == "doffer_new_1"
    with database_module.SessionLocal() as db:
        assert ledger.settlement_offers(db, 1)[0].status == "expired"
        assert db.get(ledger.BotMission, 1).status == "disputed"
        assert ledger.balance(db, ledger.ESCROW, 1, "USD") == ledger.to_money("10.00")


def test_agreement_notices_carry_amounts_buttons_and_tell_nexis_hub(monkeypatch, tmp_path, backend_db_url):
    database_module, tasks_module = _reload_backend_with_db(monkeypatch, backend_db_url)
    from backend.app import crud, ledger

    sent = []
    monkeypatch.setattr(
        tasks_module, "send_telegram_message", lambda telegram_id, text, markup=None: sent.append((telegram_id, text, markup)) or True
    )

    with database_module.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        profils_de_test.client(db, 1)
        profils_de_test.provider(db, 7, full_name="Prestataire Test")
        _paid_and_finished_mission(db, ledger, crud, 1)
        ledger.open_dispute(db, 1, acc(db, 1), "Travail bâclé")
        ledger.propose_dispute_settlement(db, 1, acc(db, 1), kind="split", provider_percentage=50)
        offer_id = ledger.settlement_offers(db, 1)[0].id

        tasks_module.notify_settlement_offer(db, offer_id, "proposed")
        [(provider, text, markup)] = sent
        assert provider == 7
        assert "4.50 USD" in text and "5.00 USD" in text and "50 %" in text
        buttons = [button["callback_data"] for button in markup["inline_keyboard"][0]]
        assert buttons == [f"doffer_ok_1_{offer_id}", f"doffer_no_1_{offer_id}"]

        sent.clear()
        ledger.accept_dispute_settlement(db, 1, offer_id, acc(db, 7))
        tasks_module.notify_settlement_offer(db, offer_id, "accepted")
        assert sorted(telegram_id for telegram_id, _, _ in sent) == [1, 900]
        client_text = next(text for telegram_id, text, _ in sent if telegram_id == 1)
        assert "5.00 USD" in client_text and "4.50 USD" in client_text
