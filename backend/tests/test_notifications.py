"""Boîte d'envoi des notifications (backend/app/notifications.py).

Ce que la table garantit : une notification par événement et par
destinataire, écrite avec l'événement (ou pas du tout), envoyée une fois
quand le fournisseur répond, renvoyée une seule fois quand on ne sait pas si
elle est partie, et signalée à l'admin quand elle ne part pas.
"""

import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app import database as _database_module  # noqa: F401,E402
from backend.app import models as _models_module  # noqa: F401,E402
from backend.tests import profils_de_test  # noqa: E402

NOW = datetime(2026, 11, 22, 10, 0, 0)


@pytest.fixture
def env(monkeypatch, backend_db_url):
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    models = importlib.reload(importlib.import_module("backend.app.models"))
    database.init_db()
    from backend.app import notifications

    fake = FakeTransport()
    monkeypatch.setattr(notifications, "_TRANSPORTS", {"telegram": fake})
    # `_ready_channels` importe notify, qui s'enregistrerait : la liste
    # remplacée ci-dessus reste la seule.
    import backend.app.notify  # noqa: F401

    return database, models, notifications, fake


class FakeTransport:
    """Expéditeur de test : rend les réponses prévues, dans l'ordre."""

    channel = "telegram"

    def __init__(self):
        self.outcomes = []
        self.sent = []
        self.ready = True

    def configured(self):
        return self.ready

    def send(self, db, notification):
        self.sent.append(notification.id)
        outcome = self.outcomes.pop(0) if self.outcomes else ("sent", "m1")
        from backend.app import notifications

        if isinstance(outcome, Exception):
            raise outcome
        kind, detail = outcome
        if kind == "sent":
            return notifications.Outcome("sent", message_id=detail)
        return notifications.Outcome(kind, error=detail)


def _person(database, telegram_id=101, language="fr"):
    with database.SessionLocal() as db:
        account_id = profils_de_test.client(db, telegram_id, language=language)
        db.commit()
        return account_id


def _enqueue(database, notifications, account_id, event_key="test_event:1", **content):
    with database.SessionLocal() as db:
        created = notifications.enqueue(
            db,
            event_key=event_key,
            account_id=account_id,
            message_key=content.pop("message_key", "admin_alert"),
            params=content.pop("params", {"text": "Bonjour"}),
            now=NOW,
            **content,
        )
        db.commit()
        return created


def _rows(database, models):
    with database.SessionLocal() as db:
        return db.query(models.Notification).order_by(models.Notification.id).all()


def test_a_notification_is_written_with_its_event_and_only_once(env):
    database, models, notifications, _fake = env
    account_id = _person(database)

    assert _enqueue(database, notifications, account_id) is True
    # Même événement rejoué (double clic, demande renvoyée) : rien de plus.
    assert _enqueue(database, notifications, account_id) is False

    rows = _rows(database, models)
    assert len(rows) == 1
    assert rows[0].status == "pending" and rows[0].channel == "telegram" and rows[0].attempts == 0


def test_a_cancelled_event_leaves_no_notification(env):
    database, models, notifications, _fake = env
    account_id = _person(database)
    with database.SessionLocal() as db:
        notifications.enqueue(db, event_key="test_event:2", account_id=account_id, message_key="admin_alert", params={"text": "x"})
        db.rollback()
    assert _rows(database, models) == []


def test_a_replayed_event_inside_a_transaction_keeps_the_transaction_usable(env):
    """Le doublon est refusé dans un point de sauvegarde : le reste de
    l'événement (ici une seconde notification) est bien validé."""
    database, models, notifications, _fake = env
    account_id = _person(database)
    other_id = _person(database, 102)
    _enqueue(database, notifications, account_id, "test_event:3")
    with database.SessionLocal() as db:
        assert notifications.enqueue(db, event_key="test_event:3", account_id=account_id, message_key="admin_alert", params={"text": "x"}) is False
        assert notifications.enqueue(db, event_key="test_event:3", account_id=other_id, message_key="admin_alert", params={"text": "x"}) is True
        db.commit()
    assert len(_rows(database, models)) == 2


def test_malformed_content_is_refused_when_written(env):
    database, _models, notifications, _fake = env
    account_id = _person(database)
    with database.SessionLocal() as db:
        with pytest.raises(ValueError):
            notifications.enqueue(db, event_key="Mauvaise clé", account_id=account_id, message_key="admin_alert")
        with pytest.raises(ValueError):
            notifications.enqueue(db, event_key="test_event:4", account_id=account_id, message_key="cle_qui_n_existe_pas")
        with pytest.raises(ValueError):
            notifications.enqueue(db, event_key="test_event:5", account_id=account_id, message_key="admin_alert", params={"text": ["liste"]})


def test_a_sent_notification_keeps_the_provider_message_id(env):
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.outcomes = [("sent", "4242")]

    report = notifications.send_due(now=NOW)

    assert report.sent == 1
    (row,) = _rows(database, models)
    assert (row.status, row.provider_message_id, row.sent_at, row.attempts) == ("sent", "4242", NOW, 1)
    # Plus jamais renvoyée.
    notifications.send_due(now=NOW + timedelta(hours=1))
    assert fake.sent == [row.id]


def test_a_safe_failure_is_retried_then_failed_after_three_attempts(env):
    """Refus avant acceptation (connexion impossible, 429, 5xx) : réessayer
    est sûr ; après 3 essais, échec et alerte de l'admin."""
    database, models, notifications, fake = env
    with database.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        db.commit()
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.outcomes = [("retry", "telegram_502"), ("retry", "telegram_502"), ("retry", "telegram_502")]

    notifications.send_due(now=NOW)
    (row,) = [r for r in _rows(database, models) if r.recipient_account_id == account_id]
    assert (row.status, row.attempts, row.next_attempt_at) == ("pending", 1, NOW + timedelta(minutes=1))
    # Pas avant l'heure prévue.
    notifications.send_due(now=NOW + timedelta(seconds=30))
    assert len(fake.sent) == 1
    notifications.send_due(now=NOW + timedelta(minutes=1))
    notifications.send_due(now=NOW + timedelta(minutes=7))

    rows = _rows(database, models)
    row = next(r for r in rows if r.recipient_account_id == account_id)
    assert (row.status, row.attempts, row.last_error) == ("failed", 3, "telegram_502")
    alerts = [r for r in rows if r.event_key == f"notification_failed:{row.id}"]
    assert len(alerts) == 1 and alerts[0].message_key == "admin_notification_failed"


def test_a_refusal_fails_at_once(env):
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.outcomes = [("refused", "telegram_403:bot was blocked by the user")]

    notifications.send_due(now=NOW)

    (row,) = [r for r in _rows(database, models) if r.recipient_account_id == account_id]
    assert (row.status, row.attempts, row.next_attempt_at) == ("failed", 1, None)


def test_an_uncertain_send_is_tried_once_more_after_fifteen_minutes(env):
    """Réponse perdue : peut-être reçue. Un seul renvoi, 15 minutes plus tard."""
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.outcomes = [("uncertain", "transport:ReadTimeout"), ("sent", "77")]

    notifications.send_due(now=NOW)
    (row,) = _rows(database, models)
    assert (row.status, row.uncertain_count, row.next_attempt_at) == ("uncertain", 1, NOW + timedelta(minutes=15))

    notifications.send_due(now=NOW + timedelta(minutes=14))
    assert len(fake.sent) == 1
    notifications.send_due(now=NOW + timedelta(minutes=15))

    (row,) = _rows(database, models)
    assert (row.status, row.provider_message_id, row.attempts) == ("sent", "77", 2)


def test_a_second_uncertainty_is_a_failure_never_a_third_send(env):
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.outcomes = [("uncertain", "transport:ReadTimeout"), ("uncertain", "transport:ReadTimeout")]

    notifications.send_due(now=NOW)
    notifications.send_due(now=NOW + timedelta(minutes=15))
    notifications.send_due(now=NOW + timedelta(hours=2))

    assert len(fake.sent) == 2
    (row,) = [r for r in _rows(database, models) if r.recipient_account_id == account_id]
    assert (row.status, row.uncertain_count) == ("failed", 2)


def test_an_unexpected_sender_error_counts_as_uncertain(env):
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    other = _enqueue(database, notifications, account_id, "test_event:other")
    assert other
    fake.outcomes = [RuntimeError("boom"), ("sent", "9")]

    report = notifications.send_due(now=NOW)

    # Une ligne en erreur n'arrête pas les autres.
    assert (report.uncertain, report.sent) == (1, 1)
    statuses = [row.status for row in _rows(database, models)]
    assert statuses == ["uncertain", "sent"]


def test_an_interrupted_send_becomes_uncertain(env):
    """Expéditeur arrêté entre « sending » et la réponse : on ne sait pas si
    le message est parti. Repris comme une incertitude, jamais renvoyé tout
    de suite."""
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    with database.SessionLocal() as db:
        row = db.query(models.Notification).one()
        row.status, row.claimed_at, row.attempts = "sending", NOW, 1
        db.commit()

    notifications.send_due(now=NOW + timedelta(minutes=1))
    (row,) = _rows(database, models)
    assert row.status == "sending" and fake.sent == []

    notifications.send_due(now=NOW + timedelta(minutes=3))
    (row,) = _rows(database, models)
    assert (row.status, row.last_error, row.next_attempt_at) == ("uncertain", "interrupted", NOW + timedelta(minutes=15))
    assert fake.sent == []


def test_an_unconfigured_sender_leaves_notifications_waiting(env):
    database, models, notifications, fake = env
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.ready = False

    notifications.send_due(now=NOW)
    (row,) = _rows(database, models)
    assert (row.status, row.attempts) == ("pending", 0) and fake.sent == []

    # Jeton refusé par Telegram en cours de route : l'essai est rendu.
    fake.ready = True
    fake.outcomes = [("unconfigured", "telegram_401")]
    notifications.send_due(now=NOW)
    (row,) = _rows(database, models)
    assert (row.status, row.attempts, row.last_error) == ("pending", 0, "telegram_401")


def test_a_person_without_reachable_channel_is_reported_at_once(env):
    database, models, notifications, _fake = env
    with database.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        account = models.NexisAccount(created_at=NOW)
        db.add(account)
        db.commit()
        account_id = account.id

    _enqueue(database, notifications, account_id)

    rows = _rows(database, models)
    row = next(r for r in rows if r.recipient_account_id == account_id)
    assert (row.status, row.channel, row.last_error) == ("failed", None, "no_channel")
    assert any(r.event_key == f"notification_failed:{row.id}" for r in rows)


def test_the_failure_of_a_failure_alert_raises_no_new_alert(env):
    database, models, notifications, fake = env
    with database.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        db.commit()
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    fake.outcomes = [("refused", "telegram_400"), ("refused", "telegram_403")]

    notifications.send_due(now=NOW)
    notifications.send_due(now=NOW)

    rows = _rows(database, models)
    assert [row.status for row in rows] == ["failed", "failed"]
    assert len(rows) == 2


def test_render_uses_the_recipient_language_and_escapes_text(env):
    database, models, notifications, _fake = env
    account_id = _person(database, 103, language="en")
    with database.SessionLocal() as db:
        notifications.enqueue(
            db,
            event_key="quote_rejected:1",
            account_id=account_id,
            message_key="quote_rejected_client",
            params={"mission_id": 7, "prestataire": "<b>Jean & fils</b>"},
            buttons=[[{"label": "yes", "action": "do_it_7"}]],
        )
        db.commit()
        row = db.query(models.Notification).one()
        rendered = notifications.render(db, row)

    from messages import get_message

    # Nombres passés tels quels (format « {mission_id:04d} » du texte),
    # chaînes échappées pour le HTML de Telegram.
    assert rendered.text == get_message("quote_rejected_client", "en", mission_id=7, prestataire="&lt;b&gt;Jean &amp; fils&lt;/b&gt;")
    assert rendered.buttons == [[(get_message("yes", "en"), "do_it_7")]]


# --- Expéditeur Telegram ---------------------------------------------------------


def _telegram(monkeypatch, env, answer):
    database, models, notifications, _fake = env
    from backend.app import notify

    monkeypatch.setattr(notify, "BOT_TOKEN", "123:abc")
    calls = []

    def post(url, json, timeout):
        calls.append((url.rsplit("/", 1)[1], json))
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer[0], json=answer[1])

    monkeypatch.setattr(notify.httpx, "post", post)
    account_id = _person(database)
    _enqueue(database, notifications, account_id)
    with database.SessionLocal() as db:
        row = db.query(models.Notification).one()
        return notify.TelegramTransport().send(db, row), calls


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        ((200, {"ok": True, "result": {"message_id": 55}}), "sent"),
        ((200, {"ok": False}), "uncertain"),
        ((429, {"ok": False, "parameters": {"retry_after": 30}}), "retry"),
        ((502, {"ok": False}), "retry"),
        ((403, {"ok": False, "description": "Forbidden: bot was blocked by the user"}), "refused"),
        ((400, {"ok": False, "description": "Bad Request: chat not found"}), "refused"),
        ((401, {"ok": False}), "unconfigured"),
        (httpx.ConnectError("refused"), "retry"),
        (httpx.ReadTimeout("slow"), "uncertain"),
        (httpx.RemoteProtocolError("cut"), "uncertain"),
    ],
)
def test_telegram_answers_are_read_safely(monkeypatch, env, answer, kind):
    outcome, calls = _telegram(monkeypatch, env, answer)
    assert outcome.kind == kind
    assert calls[0][0] == "sendMessage" and calls[0][1]["parse_mode"] == "HTML"
    if kind == "sent":
        assert outcome.message_id == "55"
    if isinstance(answer, tuple) and answer[0] == 429:
        assert outcome.retry_after == timedelta(seconds=30)


# --- Aucun envoi direct ----------------------------------------------------------


def test_nothing_writes_to_people_outside_the_notification_table():
    """Le bot ne répond qu'à la personne qui vient d'agir ; tout message à
    quelqu'un d'autre passe par la table. Seul backend/app/notify.py appelle
    l'API de Telegram depuis le backend."""
    import ast

    offenders = []
    for path in list((ROOT / "backend" / "app").rglob("*.py")):
        if path.name == "notify.py":
            continue
        if "api.telegram.org" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))
    for path in (ROOT / "telegram_bot").rglob("*.py"):
        if path.name == "webhook_watch.py":  # alertes d'infrastructure du bot lui-même
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
                continue
            if not node.func.attr.startswith("send_") or not node.args:
                continue
            if not (isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "bot"):
                continue
            target = ast.unparse(node.args[0])
            if not target.endswith("from_user.id"):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} {target}")
    assert offenders == []


def test_every_text_written_by_the_events_exists_in_the_three_languages():
    """Les notifications citent leurs textes par clé (backend/app/evenements.py) :
    chaque clé citée existe en français, lingala et anglais."""
    import json
    import re

    source = (ROOT / "backend" / "app" / "evenements.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'"([a-z][a-z0-9_]+)"', source))
    translations = {lang: json.loads((ROOT / "translations" / f"{lang}.json").read_text(encoding="utf-8")) for lang in ("fr", "ln", "en")}
    cited = {key for key in keys if key in translations["fr"]}
    # Les clés de texte citées sans être en français : faute de frappe probable.
    looks_like_text = {key for key in keys if key.endswith(("_notify", "_client", "_provider", "_admin", "_caption", "_prompt", "_alert"))}
    assert looks_like_text <= cited, sorted(looks_like_text - cited)
    assert len(cited) > 40
    for lang in ("ln", "en"):
        assert cited <= set(translations[lang]), sorted(cited - set(translations[lang]))
