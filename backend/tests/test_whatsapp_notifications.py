"""Expéditeur WhatsApp des notifications (backend/app/notify_whatsapp.py),
contre le faux serveur Meta (whatsapp_bot/fake_meta.py).

Ce qui est vérifié : message libre dans la fenêtre de 24 h, modèle validé en
dehors ; refus tardif de Meta (fenêtre fermée) qui renvoie en modèle sans
rien perdre ; réponse perdue réglée par un statut sans renvoi ; statut d'un
ancien essai écarté ; modèle en pause qui fait attendre ; échec remis à
l'équipe.
"""

import importlib
import sys
from datetime import datetime, timedelta
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.tests import profils_de_test  # noqa: E402
from whatsapp_bot.fake_meta import FakeMeta  # noqa: E402

ACCESS_TOKEN = "test-access-token-not-a-secret"
PHONE_NUMBER_ID = "100000000000001"
GRAPH_URL = "https://graph.facebook.test/v23.0"
BSUID = "CD.5000000000000000005"
PHONE = "243810000005"


class Env:
    def __init__(self, database, models, notifications, notify_whatsapp, fake):
        self.database = database
        self.models = models
        self.notifications = notifications
        self.notify_whatsapp = notify_whatsapp
        self.fake = fake

    def client(self, *, language="fr", phone=PHONE, wrote_hours_ago: float | None = 1) -> int:
        """Client WhatsApp inscrit ; `wrote_hours_ago` : son dernier message
        (pour le backend et pour Meta), None s'il n'a jamais écrit."""
        from backend.app import crud

        with self.database.SessionLocal() as db:
            account, _created = crud.register_whatsapp_client(
                db, bsuid=BSUID, display_name="Mado", language=language, phone=f"+{phone}" if phone else None
            )
            db.commit()
            account_id = account.id
        self.wrote(wrote_hours_ago, backend=True, meta=True)
        return account_id

    def wrote(self, hours_ago: float | None, *, backend: bool, meta: bool) -> None:
        if hours_ago is None:
            return
        at = datetime.utcnow() - timedelta(hours=hours_ago)
        if backend:
            with self.database.SessionLocal() as db:
                identity = db.query(self.models.ChannelIdentity).filter_by(channel="whatsapp", external_id=BSUID).one()
                identity.last_inbound_at = at
                db.commit()
        if meta:
            seen = self.fake.clock() - hours_ago * 3600
            self.fake.inbound[BSUID] = seen
            self.fake.inbound[PHONE] = seen

    def notify(self, account_id, *, key="test_event:1", message_key="new_quote_received_client", params=None, buttons=None) -> int:
        from backend.app import evenements

        if params is None:
            params = {
                "mission_id": 42,
                "prestataire": "Jean <b>& fils</b>",
                "trust_line": {"$trust": {"total_missions": 0}},
                "amount": 40.0,
                "currency": "USD",
                "delay": 4,
                "message": "Je passe ce soir",
            }
        if buttons is None:
            buttons = evenements.quote_buttons(7)
        with self.database.SessionLocal() as db:
            self.notifications.enqueue(db, event_key=key, account_id=account_id, message_key=message_key, params=params, buttons=buttons)
            db.commit()
            return db.query(self.models.Notification).filter_by(event_key=key, recipient_account_id=account_id).one().id

    def send(self, *, minutes_later: float = 0):
        return self.notifications.send_due(now=datetime.utcnow() + timedelta(minutes=minutes_later))

    def row(self, notification_id):
        with self.database.SessionLocal() as db:
            return db.get(self.models.Notification, notification_id)

    def status(self, sent, status, *, error_code=None, attempt_callback=None):
        """Statut relayé par le service WhatsApp (comme /api/whatsapp/statuses)."""
        with self.database.SessionLocal() as db:
            result = self.notify_whatsapp.apply_status(
                db,
                callback=attempt_callback or sent.callback,
                message_id=sent.wamid,
                status=status,
                error_code=error_code,
                now=datetime.utcnow(),
            )
            db.commit()
            return result


@pytest.fixture
def env(monkeypatch, backend_db_url):
    importlib.import_module("backend.app.main")
    monkeypatch.setenv("DATABASE_URL", backend_db_url)
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", ACCESS_TOKEN)
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", PHONE_NUMBER_ID)
    monkeypatch.setenv("WHATSAPP_GRAPH_URL", GRAPH_URL)
    database = importlib.reload(importlib.import_module("backend.app.database"))
    models = importlib.reload(importlib.import_module("backend.app.models"))
    database.init_db()
    from backend.app import notifications, notify_whatsapp

    fake = FakeMeta(access_token=ACCESS_TOKEN, phone_number_id=PHONE_NUMBER_ID, app_secret="secret-not-used")
    api = TestClient(fake.app())

    def post(url, json, headers, timeout):
        return api.post(url, json=json, headers=headers)

    monkeypatch.setattr(notify_whatsapp, "_http_post", post)
    monkeypatch.setattr(notifications, "_TRANSPORTS", {"whatsapp": notify_whatsapp.WhatsAppTransport()})
    return Env(database, models, notifications, notify_whatsapp, fake)


# --- Dans la fenêtre : message libre -----------------------------------------------------


def test_inside_the_window_the_full_text_leaves_with_its_buttons(env):
    account_id = env.client(wrote_hours_ago=2)
    notification_id = env.notify(account_id)
    assert env.send().sent == 1

    (sent,) = env.fake.sent
    assert sent.kind == "button" and sent.to == PHONE
    assert [action for action, _label in sent.choices] == ["quote_accept_7", "quote_reject_7"]
    assert all(len(label) <= 20 for _action, label in sent.choices)
    # Gras de Telegram converti, valeur écrite par une personne gardée telle quelle.
    assert "*NXH-0042*" in sent.text and "Jean <b>& fils</b>" in sent.text and "<b>Nouveau" not in sent.text
    assert sent.callback == f"nexis:{notification_id}:1"
    row = env.row(notification_id)
    assert row.status == "sent" and row.provider_message_id == sent.wamid and not row.template_required


def test_buttons_the_whatsapp_service_does_not_know_are_not_shown(env):
    account_id = env.client()
    env.notify(account_id, message_key="app_new_device_alert", params={"device": "Pixel", "date": "01/12/2026", "time": "10:00"},
               buttons=[[{"label": "button_app_not_me", "action": "app_not_me_3"}]])
    env.send()
    (sent,) = env.fake.sent
    assert sent.kind == "text" and "Pixel" in sent.text


def test_without_a_phone_the_whatsapp_identity_is_the_address(env):
    account_id = env.client(phone=None)
    env.notify(account_id)
    env.send()
    (sent,) = env.fake.sent
    assert sent.to is None and sent.recipient == BSUID


# --- Hors fenêtre : modèle validé ------------------------------------------------------------


@pytest.mark.parametrize(("language", "template_language", "phrase"), [
    ("fr", "fr", "Vous avez reçu un devis pour votre demande NXH-0042."),
    ("ln", "fr", "Vous avez reçu un devis pour votre demande NXH-0042."),
    ("en", "en", "You have received a quote for your request NXH-0042."),
])
def test_outside_the_window_the_approved_template_leaves(env, language, template_language, phrase):
    account_id = env.client(language=language, wrote_hours_ago=30)
    notification_id = env.notify(account_id)
    assert env.send().sent == 1

    (sent,) = env.fake.sent
    template = sent.template
    assert template["name"] == "nexis_suivi" and template["language"] == {"code": template_language}
    body, button = template["components"]
    assert body["parameters"] == [{"type": "text", "text": phrase}]
    assert button["sub_type"] == "quick_reply" and button["parameters"] == [{"type": "payload", "payload": "mis:42"}]
    assert env.row(notification_id).status == "sent"
    assert env.fake.statuses and env.fake.statuses[0]["status"] == "delivered"


def test_someone_who_never_wrote_gets_the_template(env):
    account_id = env.client(wrote_hours_ago=None)
    env.notify(account_id)
    env.send()
    assert env.fake.sent[0].template is not None


def test_a_template_button_without_a_request_opens_the_balance_or_the_list(env):
    from backend.app import modeles_whatsapp

    assert modeles_whatsapp.button_payload("payout_succeeded", {"amount": "10.00"}) == "menu:wallet"
    assert modeles_whatsapp.button_payload("client_need_accepted", {"reference": "BES-0001"}) == "menu:missions"
    assert modeles_whatsapp.phrase("client_need_accepted", {"reference": "BES-0001"}, "fr") == "NexisHub a répondu à votre besoin BES-0001."
    assert modeles_whatsapp.phrase("texte_inconnu", {"mission_id": 3}, "en") == "There is an update on your request NXH-0003."


def test_every_phrase_fits_a_template_variable():
    """Meta refuse saut de ligne, tabulation et 5 espaces dans une variable."""
    from backend.app import modeles_whatsapp

    for key, texts in modeles_whatsapp.PHRASES.items():
        for lang in ("fr", "ln", "en"):
            text = modeles_whatsapp.phrase(key, {"mission_id": 12, "reference": "BES-0001"}, lang)
            assert text and "\n" not in text and "\t" not in text and "     " not in text and len(text) < 300, key
    for language in ("fr", "en"):
        submission = modeles_whatsapp.submission(language)
        assert submission["category"] == "UTILITY"
        assert submission["components"][0]["text"].count("{{1}}") == 1
        assert len(modeles_whatsapp.BUTTON[language]) <= 25


# --- Meta refuse après coup : fenêtre fermée ----------------------------------------------


def test_a_free_message_refused_later_for_the_closed_window_leaves_again_as_a_template(env):
    """Le backend croit la fenêtre ouverte (heure notée), Meta non : le message
    est accepté puis refusé par un statut 131047. Rien n'est arrivé : le
    modèle part, une seule fois."""
    account_id = env.client(wrote_hours_ago=2)
    env.wrote(30, backend=False, meta=True)
    notification_id = env.notify(account_id)
    env.send()
    (free,) = env.fake.sent
    assert free.kind == "button" and env.row(notification_id).status == "sent"

    (failed,) = env.fake.statuses
    assert failed["status"] == "failed" and failed["errors"][0]["code"] == 131047
    assert env.status(free, "failed", error_code=131047) == "template"
    row = env.row(notification_id)
    assert row.status == "pending" and row.template_required and row.sent_at is None
    # Le même statut relayé deux fois ne refait rien.
    assert env.status(free, "failed", error_code=131047) == "ignored"

    assert env.send().sent == 1
    template = env.fake.sent[-1]
    assert template.template is not None and template.callback == f"nexis:{notification_id}:2"
    assert env.status(template, "delivered") == "ignored"  # déjà noté envoyé, même wamid
    row = env.row(notification_id)
    assert row.status == "sent" and row.provider_message_id == template.wamid
    assert env.send(minutes_later=30).sent == 0


def test_a_failure_for_another_reason_goes_to_the_team(env):
    with env.database.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        db.commit()
    account_id = env.client()
    notification_id = env.notify(account_id)
    env.send()
    sent = env.fake.sent[0]
    assert env.status(sent, "failed", error_code=131026) == "failed"
    row = env.row(notification_id)
    assert row.status == "failed" and row.sent_at is None and row.last_error == "whatsapp_status:131026"
    with env.database.SessionLocal() as db:
        alerts = db.query(env.models.Notification).filter(env.models.Notification.event_key.like("notification_failed:%")).all()
        assert [alert.params["notification_id"] for alert in alerts] == [notification_id]


# --- Réponse perdue -------------------------------------------------------------------------


def test_a_lost_answer_is_settled_by_the_status_without_sending_again(env):
    account_id = env.client()
    notification_id = env.notify(account_id)
    env.fake.fail_next("timeout")
    assert env.send().uncertain == 1
    row = env.row(notification_id)
    assert row.status == "uncertain" and env.fake.sent == []

    # Meta avait bien reçu (le faux Meta coupe avant d'enregistrer : on
    # rejoue comme si le message était parti, avec le même essai).
    from whatsapp_bot.fake_meta import Sent

    ghost = Sent(wamid="wamid.LOST0001", to=PHONE, recipient=None, body={"biz_opaque_callback_data": f"nexis:{notification_id}:1"})
    assert env.status(ghost, "delivered") == "confirmed"
    row = env.row(notification_id)
    assert row.status == "sent" and row.provider_message_id == "wamid.LOST0001"
    assert env.send(minutes_later=20).sent == 0 and env.fake.sent == []


def test_a_late_status_from_an_older_attempt_is_ignored(env):
    account_id = env.client()
    notification_id = env.notify(account_id)
    env.fake.fail_next("timeout")
    env.send()
    assert env.send(minutes_later=16).sent == 1  # seul renvoi permis, essai 2
    second = env.fake.sent[-1]
    assert second.callback == f"nexis:{notification_id}:2"

    from whatsapp_bot.fake_meta import Sent

    first = Sent(wamid="wamid.OLD00001", to=PHONE, recipient=None, body={"biz_opaque_callback_data": f"nexis:{notification_id}:1"})
    assert env.status(first, "failed", error_code=131026) == "ignored"
    assert env.row(notification_id).status == "sent"
    assert env.status(second, "delivered") == "ignored"


def test_a_status_for_an_unknown_or_foreign_message_is_ignored(env):
    from whatsapp_bot.fake_meta import Sent

    account_id = env.client()
    notification_id = env.notify(account_id)
    env.send()
    other = Sent(wamid="wamid.OTHER001", to=PHONE, recipient=None, body={"biz_opaque_callback_data": f"nexis:{notification_id}:1"})
    assert env.status(other, "failed", error_code=131026) == "ignored"
    nowhere = Sent(wamid="wamid.X", to=PHONE, recipient=None, body={"biz_opaque_callback_data": "nexis:999999:1"})
    assert env.status(nowhere, "delivered") == "ignored"
    assert env.status(nowhere, "delivered", attempt_callback="autre:1:1") == "ignored"
    assert env.row(notification_id).status == "sent"


# --- Modèle en pause, refus et pannes de Meta ----------------------------------------------


def test_a_paused_template_makes_notifications_wait_without_counting(env):
    account_id = env.client(wrote_hours_ago=30)
    notification_id = env.notify(account_id)
    env.fake.templates[("nexis_suivi", "fr")] = "PAUSED"
    report = env.send()
    assert report.waiting == 1 and env.fake.sent == []
    row = env.row(notification_id)
    assert row.status == "pending" and row.attempts == 0 and row.last_error == "whatsapp_400:132015"

    env.fake.templates[("nexis_suivi", "fr")] = "APPROVED"
    assert env.send(minutes_later=2).sent == 1


@pytest.mark.parametrize(
    ("answer", "kind"),
    [
        ((200, {"messages": [{"id": "wamid.A"}]}), "sent"),
        ((200, {}), "uncertain"),
        ((500, {"error": {"code": 2}}), "uncertain"),
        ((429, {"error": {"code": 130429}}), "retry"),
        ((400, {"error": {"code": 131056}}), "retry"),
        ((400, {"error": {"code": 131047}}), "needs_template"),
        ((401, {"error": {"code": 190}}), "unconfigured"),
        ((404, {"error": {"code": 132001}}), "unconfigured"),
        ((400, {"error": {"code": 131026}}), "refused"),
        (httpx.ConnectError("refused"), "retry"),
        (httpx.ReadTimeout("slow"), "uncertain"),
    ],
)
def test_meta_answers_are_read_safely(env, monkeypatch, answer, kind):
    def post(url, json, headers, timeout):
        if isinstance(answer, Exception):
            raise answer
        return httpx.Response(answer[0], json=answer[1])

    monkeypatch.setattr(env.notify_whatsapp, "_http_post", post)
    account_id = env.client()
    env.notify(account_id)
    with env.database.SessionLocal() as db:
        row = db.query(env.models.Notification).one()
        row.attempts = 1
        outcome = env.notify_whatsapp.WhatsAppTransport().send(db, row)
    assert outcome.kind == kind


def test_not_configured_means_waiting(env, monkeypatch):
    monkeypatch.delenv("WHATSAPP_ACCESS_TOKEN")
    account_id = env.client()
    notification_id = env.notify(account_id)
    env.send()
    assert env.fake.sent == [] and env.row(notification_id).status == "pending"


def test_telegram_html_becomes_whatsapp_text():
    from backend.app.notify_whatsapp import whatsapp_text

    assert whatsapp_text("💬 <b>Nouveau</b> <i>devis</i>\nPrix : <b>1 &lt; 2 &amp; 3</b> <a href='x'>lien</a>") == (
        "💬 *Nouveau* _devis_\nPrix : *1 < 2 & 3* lien"
    )


# --- Événements du compte ------------------------------------------------------------------


def test_a_template_event_reaches_the_team_once(env):
    with env.database.SessionLocal() as db:
        profils_de_test.admin(db, 900)
        db.commit()
    value = {"event": "PAUSED", "message_template_name": "nexis_suivi", "message_template_language": "fr", "reason": "<script>"}
    for _ in range(2):
        with env.database.SessionLocal() as db:
            env.notify_whatsapp.alert_meta_event(db, "message_template_status_update", value, now=datetime.utcnow())
            db.commit()
    with env.database.SessionLocal() as db:
        alerts = db.query(env.models.Notification).filter(env.models.Notification.event_key.like("whatsapp_meta:%")).all()
    assert len(alerts) == 1
    text = alerts[0].params["text"]["$html"]
    assert "nexis_suivi" in text and "mis en pause" in text and "&lt;script&gt;" in text and "attendent" in text
