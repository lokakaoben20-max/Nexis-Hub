"""Lecture de la boîte d'envoi (table `notifications`) dans les tests.

Les messages aux personnes sont écrits dans la table avec l'événement
(backend/app/evenements.py) ; un test lit ce qui a été écrit, rédigé comme
il partira (langue du destinataire, HTML de Telegram), sans rien envoyer.
"""

from dataclasses import dataclass


@dataclass
class Message:
    id: int
    event_key: str
    telegram_id: int | None
    message_key: str
    text: str
    buttons: list
    media: dict | None
    status: str

    @property
    def actions(self) -> list[str]:
        return [action for row in self.buttons for _label, action in row]


def messages(db, *, telegram_id: int | None = None, event_prefix: str | None = None) -> list[Message]:
    """Notifications écrites, dans l'ordre de création. `telegram_id` : celles
    d'une personne ; `event_prefix` : celles d'un type d'événement."""
    from backend.app import models, notifications

    rows = db.query(models.Notification).order_by(models.Notification.id).all()
    found = []
    for row in rows:
        identity = (
            db.query(models.ChannelIdentity.external_id)
            .filter(models.ChannelIdentity.account_id == row.recipient_account_id, models.ChannelIdentity.channel == "telegram")
            .one_or_none()
        )
        recipient = int(identity[0]) if identity is not None and identity[0].lstrip("-").isdigit() else None
        if telegram_id is not None and recipient != telegram_id:
            continue
        if event_prefix is not None and not row.event_key.startswith(event_prefix):
            continue
        rendered = notifications.render(db, row)
        found.append(
            Message(row.id, row.event_key, recipient, row.message_key, rendered.text, rendered.buttons, rendered.media, row.status)
        )
    return found


def recipients(db, **filters) -> list[int | None]:
    return [message.telegram_id for message in messages(db, **filters)]


class TelegramRecorder:
    """Expéditeur Telegram de test : la vraie mise en forme
    (backend/app/notify.py), sans appel réseau. Garde (destinataire, texte,
    boutons) ; une photo est notée « [photo <id>] <légende> ». `refuse` :
    méthodes de l'API que Telegram refuse (ex. {"sendPhoto"})."""

    def __init__(self, on_send=None):
        from backend.app import notify

        recorder = self

        class _Transport(notify.TelegramTransport):
            def configured(self):
                return True

            def _call(self, method, content, markup, *, parse=True):
                from backend.app import notifications

                if method in recorder.refuse:
                    return notifications.Outcome("refused", error=f"telegram_400:{method}")
                if method == "sendMessage":
                    text = content["text"]
                elif method == "sendVideoNote":
                    text = f"[video_note {content['video_note']}]"
                else:
                    field = {"sendPhoto": "photo", "sendVoice": "voice"}[method]
                    text = f"[{field} {content[field]}] {content['caption']}"
                recorder.count += 1
                recorder.on_send(int(content["chat_id"]), text, markup)
                return notifications.Outcome("sent", message_id=str(recorder.count))

        self.transport = _Transport()
        self.sent: list = []
        self.refuse: set = set()
        self.count = 0
        self.on_send = on_send or (lambda chat_id, text, markup: self.sent.append((chat_id, text, markup)))

    def deliver(self) -> list:
        """Envoie ce qui attend dans la boîte d'envoi ; rend les messages partis."""
        from backend.app import notifications

        notifications.send_due()
        return self.sent


def record_telegram(monkeypatch, on_send=None) -> TelegramRecorder:
    """Branche l'expéditeur de test. `on_send(chat_id, texte, boutons)` :
    au lieu de garder les messages dans `recorder.sent`."""
    from backend.app import notifications

    recorder = TelegramRecorder(on_send)
    monkeypatch.setattr(notifications, "_TRANSPORTS", {notifications.TELEGRAM: recorder.transport})
    return recorder
