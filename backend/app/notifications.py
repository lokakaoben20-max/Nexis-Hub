"""Notifications fiables : boîte d'envoi en base (étape 3 du plan WhatsApp,
docs/ARCHITECTURE_WHATSAPP.md, « Routage des notifications »).

Pourquoi une table
------------------
Avant, chaque message partait directement vers Telegram après l'événement
(bot ou tâche planifiée). Un processus arrêté entre la validation de
l'événement et l'envoi perdait le message, en silence. Ici :

1. **Création** (`enqueue`) : la notification est ajoutée à la session de
   l'événement, **sans valider**. L'appelant valide l'événement et la
   notification ensemble ; si l'événement est annulé, elle disparaît avec lui.
   Une seule notification par événement et par destinataire (contrainte
   d'unicité) : un événement rejoué n'en crée pas une seconde.
2. **Envoi** (`send_due`) : un expéditeur prend les notifications dues sous
   verrou de ligne (`FOR UPDATE SKIP LOCKED` : deux expéditeurs ne prennent
   jamais la même), les note `sending` et valide **avant** d'appeler
   Telegram ou Meta, puis note ce qu'il a appris.

États
-----
- `pending` : à envoyer (au plus tôt à `next_attempt_at`) ;
- `sending` : requête partie ou sur le point de partir ;
- `sent` : acceptée par le fournisseur (identifiant de message gardé) ;
- `uncertain` : requête partie sans réponse (délai dépassé, connexion coupée,
  ou expéditeur arrêté pendant l'envoi). On ne sait pas si le message est
  arrivé : **une seule** nouvelle tentative, après 15 minutes. Sur WhatsApp,
  un statut de Meta qui porte l'identifiant de la notification
  (`biz_opaque_callback_data`, étape 8) la passe à `sent` sans renvoi ;
- `failed` : refus explicite du fournisseur (personne qui a bloqué le bot,
  numéro invalide), 3 échecs, ou seconde incertitude. L'admin est prévenu.

Un doublon à l'arrivée reste possible dans le cas rare d'une incertitude
suivie d'un renvoi ; il est sans conséquence : les textes nomment la mission
et l'état, jamais une instruction, et aucune notification ne porte d'action
d'argent (l'argent est décidé avant elle). La personne retrouve toujours
l'état exact par « Mes missions » ou « Mon solde ».

Canal
-----
Celui du destinataire, choisi à la création (`recipient_channel`), jamais
celui de l'événement : un client WhatsApp reçoit sur WhatsApp le devis d'un
prestataire Telegram. Un canal dont l'expéditeur n'est pas configuré (jeton
absent, ou WhatsApp avant l'étape 8) n'est pas tenté : ses notifications
attendent, sans compter d'essai.

Contenu
-------
Clé de traduction + paramètres, rédigés à l'envoi dans la langue du
destinataire et au format de son canal (`render`). Un paramètre est une
valeur simple (échappée pour le HTML de Telegram) ou une valeur typée :

- ``{"$service": clé}`` : nom du service dans la langue du destinataire ;
- ``{"$services": [clés]}`` : plusieurs services, séparés par des virgules ;
- ``{"$yes_no": bool}`` : Oui / Non ;
- ``{"$message": clé}`` : un autre texte traduit ;
- ``{"$html": texte}`` : texte déjà sûr, écrit par le backend (alertes admin) ;
- ``{"$trust": {...}}`` : ligne de confiance d'un prestataire.

Boutons : lignes de ``{"label": clé de traduction, "action": identifiant}``.
L'identifiant sert de `callback_data` Telegram et d'identifiant de bouton
WhatsApp.

Aucun texte de message n'est écrit dans les journaux (seulement les
identifiants de notification et les erreurs).
"""

from __future__ import annotations

import contextvars
import html
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Protocol

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app import database
from backend.app.models import AdminRole, ChannelIdentity, NexisAccount, Notification, Service
from messages import get_message

logger = logging.getLogger("nexis.notifications")

TELEGRAM = "telegram"
WHATSAPP = "whatsapp"
CHANNELS = (TELEGRAM, WHATSAPP)
LANGUAGES = ("fr", "ln", "en")

PENDING, SENDING, SENT, UNCERTAIN, FAILED = "pending", "sending", "sent", "uncertain", "failed"

MAX_ATTEMPTS = 3
# Délai avant le seul renvoi d'une notification incertaine.
UNCERTAIN_RETRY_AFTER = timedelta(minutes=15)
# Un envoi noté `sending` depuis plus longtemps a été interrompu
# (expéditeur arrêté) : il devient incertain. Bien plus long que le délai
# d'un appel (10 s).
SENDING_STALE_AFTER = timedelta(minutes=2)
# Attente avant un nouvel essai après un échec sûr (requête refusée avant
# d'être acceptée) : 1 min, puis 5 min.
RETRY_DELAYS = (timedelta(minutes=1), timedelta(minutes=5))
BATCH_SIZE = 100

# Événement d'une alerte « notification non envoyée » : jamais d'alerte sur
# l'échec d'une de ces alertes (pas de boucle).
FAILURE_ALERT_PREFIX = "notification_failed:"

_EVENT_KEY = re.compile(r"[a-z0-9_]+(:[A-Za-z0-9_.-]+)*")
_ACTION = re.compile(r"[A-Za-z0-9_:.-]{1,64}")
MEDIA_KINDS = ("photo", "voice", "video_note")


def _utcnow() -> datetime:
    return datetime.utcnow()


# --- Création ------------------------------------------------------------------


def recipient_channel(db: Session, account_id: int) -> str | None:
    """Canal par lequel joindre la personne : Telegram si elle y est, sinon
    WhatsApp. Un compte ne porte aujourd'hui qu'un seul de ces deux canaux
    (la liaison des deux arrive à l'étape 9, avec le choix de la personne).
    None : aucun canal joignable (compte de l'app seule)."""
    channels = {
        channel
        for (channel,) in db.query(ChannelIdentity.channel).filter(
            ChannelIdentity.account_id == account_id, ChannelIdentity.channel.in_(CHANNELS)
        )
    }
    for channel in CHANNELS:
        if channel in channels:
            return channel
    return None


def _check_content(event_key: str, message_key: str, params: dict, buttons: list, media: dict | None) -> None:
    """Refus d'une notification mal formée, au moment où elle est écrite
    (bug du code appelant) plutôt qu'à l'envoi."""
    if not _EVENT_KEY.fullmatch(event_key) or len(event_key) > 120:
        raise ValueError(f"Clé d'événement invalide : {event_key!r}")
    if get_message(message_key, "fr").startswith("[Message manquant"):
        raise ValueError(f"Texte inconnu : {message_key}")
    for value in params.values():
        _check_param(value)
    for row in buttons:
        for button in row:
            if set(button) != {"label", "action"} or not _ACTION.fullmatch(button["action"]):
                raise ValueError(f"Bouton invalide : {button!r}")
            if get_message(button["label"], "fr").startswith("[Message manquant"):
                raise ValueError(f"Libellé de bouton inconnu : {button['label']}")
    if media is not None:
        if (
            not set(media) <= {"kind", "channel", "id", "optional"}
            or media.get("kind") not in MEDIA_KINDS
            or media.get("channel") not in CHANNELS
            or not isinstance(media.get("id"), str)
            or not media["id"]
        ):
            raise ValueError(f"Pièce jointe invalide : {media!r}")


def _check_param(value) -> None:
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, dict) and len(value) == 1:
        (kind, inner), = value.items()
        if kind in ("$service", "$message", "$html") and isinstance(inner, str):
            return
        if kind == "$services" and isinstance(inner, list) and all(isinstance(key, str) for key in inner):
            return
        if kind == "$yes_no" and isinstance(inner, bool):
            return
        if kind == "$trust" and isinstance(inner, dict):
            return
    raise ValueError(f"Paramètre de notification invalide : {value!r}")


@dataclass
class _Pending:
    """Notifications ajoutées pendant la demande HTTP en cours : à envoyer
    juste après la réponse (`backend.app.main`)."""

    added: bool = False


_REQUEST = contextvars.ContextVar("nexis_notifications_request", default=None)


def begin_request() -> tuple[_Pending, contextvars.Token]:
    pending = _Pending()
    return pending, _REQUEST.set(pending)


def end_request(token: contextvars.Token) -> None:
    _REQUEST.reset(token)


def enqueue(
    db: Session,
    *,
    event_key: str,
    account_id: int | None,
    message_key: str,
    params: dict | None = None,
    buttons: list | None = None,
    media: dict | None = None,
    now: datetime | None = None,
) -> bool:
    """Ajoute la notification à la transaction en cours, sans valider. Rend
    False si elle existait déjà (événement rejoué) ou s'il n'y a personne à
    prévenir (`account_id` None)."""
    if account_id is None:
        return False
    params, buttons = dict(params or {}), [list(row) for row in (buttons or [])]
    _check_content(event_key, message_key, params, buttons, media)
    now = now or _utcnow()
    channel = recipient_channel(db, account_id)
    notification = Notification(
        event_key=event_key,
        recipient_account_id=account_id,
        channel=channel,
        message_key=message_key,
        params=params,
        buttons=buttons,
        media=media,
        status=PENDING if channel else FAILED,
        attempts=0,
        uncertain_count=0,
        created_at=now,
        next_attempt_at=now if channel else None,
        last_error=None if channel else "no_channel",
    )
    try:
        # Point de sauvegarde : un doublon n'annule pas l'événement qui l'a causé.
        with db.begin_nested():
            db.add(notification)
            db.flush()
    except IntegrityError:
        return False
    if channel is None:
        logger.error("Notification %s : compte %s sans canal joignable", notification.id, account_id)
        _alert_failure(db, notification, now)
    pending = _REQUEST.get()
    if pending is not None:
        pending.added = True
    return True


def withdraw(db: Session, event_key: str) -> int:
    """Retire les notifications d'un événement qui n'ont pas encore été
    tentées et ne servent plus (ex. alerte « Nouvel appareil » d'un téléphone
    déjà coupé). Une notification déjà partie ou peut-être partie reste.
    Dans la transaction de l'appelant ; rend le nombre retiré."""
    return (
        db.query(Notification)
        .filter(Notification.event_key == event_key, Notification.status == PENDING)
        .delete(synchronize_session=False)
    )


def admin_account_ids(db: Session) -> list[int]:
    rows = (
        db.query(AdminRole.account_id)
        .filter(AdminRole.revoked_at.is_(None))
        .order_by(AdminRole.granted_at, AdminRole.id)
        .all()
    )
    return [account_id for (account_id,) in rows]


def enqueue_admins(
    db: Session,
    *,
    event_key: str,
    message_key: str = "admin_alert",
    params: dict | None = None,
    buttons: list | None = None,
    media: dict | None = None,
    except_account_id: int | None = None,
    now: datetime | None = None,
) -> int:
    """Même notification pour chaque admin actif. Rend le nombre d'admins
    visés ; sans admin enregistré, l'erreur est journalisée (personne ne
    serait prévenu)."""
    recipients = [account_id for account_id in admin_account_ids(db) if account_id != except_account_id]
    if not recipients and except_account_id is None:
        logger.error("Alerte admin %s non enregistrée : aucun admin (python -m backend.app.admins)", event_key)
    for account_id in recipients:
        enqueue(
            db, event_key=event_key, account_id=account_id, message_key=message_key,
            params=params, buttons=buttons, media=media, now=now,
        )
    return len(recipients)


def admin_text(text: str) -> dict:
    """Paramètre d'alerte admin : texte écrit par le backend, déjà échappé."""
    return {"text": {"$html": text}}


def _alert_failure(db: Session, notification: Notification, now: datetime) -> None:
    if notification.event_key.startswith(FAILURE_ALERT_PREFIX):
        return
    enqueue_admins(
        db,
        event_key=f"{FAILURE_ALERT_PREFIX}{notification.id}",
        message_key="admin_notification_failed",
        params={
            "notification_id": notification.id,
            "account_id": notification.recipient_account_id,
            "event": notification.event_key,
            "error": notification.last_error or "",
        },
        now=now,
    )


# --- Rédaction -------------------------------------------------------------------


@dataclass(frozen=True)
class Rendered:
    """Message prêt pour un canal : texte (HTML pour Telegram), boutons
    (lignes de (libellé, action)) et pièce jointe éventuelle."""

    text: str
    buttons: list[list[tuple[str, str]]] = field(default_factory=list)
    media: dict | None = None


def language_of(db: Session, account_id: int) -> str:
    account = db.get(NexisAccount, account_id)
    return account.language if account is not None and account.language in LANGUAGES else "fr"


def _service_label(db: Session, key: str, lang: str) -> str:
    service = db.get(Service, key)
    if service is None:
        return key
    name = getattr(service, f"name_{lang}", None) or service.name_fr
    return f"{service.icon_emoji or ''} {name}".strip()


def trust_line(trust: dict, lang: str) -> str:
    """Ligne de confiance d'un prestataire montrée avec son devis (note,
    missions, réussite, badge, vérifié)."""
    if not trust.get("total_missions"):
        return get_message("trust_new_provider", lang)
    line = get_message(
        "trust_line",
        lang,
        rating=f"{float(trust.get('rating') or 0):.1f}",
        missions=int(trust["total_missions"]),
        success=f"{float(trust.get('success_rate') or 0):.0f}",
    )
    badge = trust.get("badge")
    if badge in ("partner", "expert", "premium", "verified"):
        line += f" · {get_message(f'trust_badge_{badge}', lang)}"
    if trust.get("is_verified"):
        line += f" · {get_message('trust_verified', lang)}"
    return line


def _param(db: Session, value, lang: str, escape):
    if isinstance(value, dict):
        (kind, inner), = value.items()
        if kind == "$service":
            return escape(_service_label(db, inner, lang))
        if kind == "$services":
            return escape(", ".join(_service_label(db, key, lang) for key in inner))
        if kind == "$yes_no":
            return get_message("yes" if inner else "no", lang)
        if kind == "$message":
            return get_message(inner, lang)
        if kind == "$html":
            return inner
        if kind == "$trust":
            return escape(trust_line(inner, lang))
    if value is None:
        return ""
    if isinstance(value, (bool, int, float)):
        # Les textes formatent eux-mêmes les nombres ({mission_id:04d}, {amount:.2f}).
        return value
    return escape(str(value))


def render(db: Session, notification: Notification, lang: str | None = None, *, escape=html.escape) -> Rendered:
    """Texte de la notification dans la langue du destinataire. `escape` :
    échappement des valeurs pour le format du canal (HTML pour Telegram)."""
    lang = lang or language_of(db, notification.recipient_account_id)
    values = {name: _param(db, value, lang, escape) for name, value in (notification.params or {}).items()}
    text = get_message(notification.message_key, lang, **values)
    buttons = [
        [(get_message(button["label"], lang), button["action"]) for button in row] for row in (notification.buttons or [])
    ]
    return Rendered(text=text, buttons=buttons, media=notification.media)


# --- Envoi -----------------------------------------------------------------------


@dataclass(frozen=True)
class Outcome:
    """Ce qu'un fournisseur a répondu à un envoi.

    - `sent` : accepté (`message_id` gardé) ;
    - `retry` : refusé avant d'être accepté (fournisseur injoignable avant
      l'envoi, surcharge, erreur du fournisseur) : on peut réessayer ;
    - `uncertain` : requête partie, réponse perdue ;
    - `refused` : refus définitif (personne qui a bloqué le bot...) ;
    - `unconfigured` : l'expéditeur ne peut rien envoyer (jeton absent ou
      refusé) : la notification attend, sans compter d'essai."""

    kind: str
    message_id: str | None = None
    error: str | None = None
    retry_after: timedelta | None = None


class Transport(Protocol):
    channel: str

    def configured(self) -> bool: ...

    def send(self, db: Session, notification: Notification) -> Outcome: ...


_TRANSPORTS: dict[str, Transport] = {}


def register_transport(transport: Transport) -> None:
    _TRANSPORTS[transport.channel] = transport


def transport_for(channel: str) -> Transport | None:
    return _TRANSPORTS.get(channel)


def _ready_channels() -> list[str]:
    # Expéditeurs connus : Telegram (backend/app/notify.py). Importé ici pour
    # que tout processus qui envoie l'ait enregistré.
    from backend.app import notify  # noqa: F401

    return [channel for channel, transport in _TRANSPORTS.items() if transport.configured()]


@dataclass
class Report:
    sent: int = 0
    retried: int = 0
    uncertain: int = 0
    failed: int = 0
    waiting: int = 0


def recover_interrupted(db: Session, now: datetime) -> int:
    """Envois notés `sending` depuis trop longtemps (expéditeur arrêté
    pendant l'appel) : on ne sait pas si le message est parti, ils deviennent
    incertains. Rend le nombre de notifications reprises."""
    stale = (
        db.query(Notification)
        .filter(Notification.status == SENDING, Notification.claimed_at < now - SENDING_STALE_AFTER)
        .with_for_update(skip_locked=True)
        .all()
    )
    for notification in stale:
        _note_uncertain(db, notification, "interrupted", now)
    db.commit()
    return len(stale)


def _note_uncertain(db: Session, notification: Notification, error: str, now: datetime) -> None:
    notification.uncertain_count += 1
    notification.last_error = error[:200]
    if notification.uncertain_count >= 2:
        _note_failed(db, notification, error, now)
        return
    notification.status = UNCERTAIN
    notification.next_attempt_at = (notification.claimed_at or now) + UNCERTAIN_RETRY_AFTER


def _note_failed(db: Session, notification: Notification, error: str, now: datetime) -> None:
    notification.status = FAILED
    notification.next_attempt_at = None
    notification.last_error = error[:200]
    logger.error("Notification %s non envoyée (%s)", notification.id, error)
    _alert_failure(db, notification, now)


def _claim(db: Session, now: datetime, channels: list[str], limit: int) -> list[tuple[int, datetime]]:
    """Prend les notifications dues sous verrou, les note `sending` et valide
    avant tout appel au fournisseur."""
    rows = (
        db.query(Notification)
        .filter(
            Notification.status.in_((PENDING, UNCERTAIN)),
            Notification.next_attempt_at <= now,
            Notification.channel.in_(channels),
        )
        .order_by(Notification.id)
        .limit(limit)
        .with_for_update(skip_locked=True)
        .all()
    )
    claimed = []
    for notification in rows:
        notification.status = SENDING
        notification.claimed_at = now
        notification.attempts += 1
        claimed.append((notification.id, now))
    db.commit()
    return claimed


def mark_sent(db: Session, notification: Notification, message_id: str | None, now: datetime) -> None:
    notification.status = SENT
    notification.sent_at = now
    notification.next_attempt_at = None
    notification.provider_message_id = (message_id or "")[:200] or None
    notification.last_error = None


def _apply(db: Session, notification: Notification, outcome: Outcome, now: datetime, report: Report) -> None:
    if outcome.kind == "sent":
        mark_sent(db, notification, outcome.message_id, now)
        report.sent += 1
    elif outcome.kind == "uncertain":
        _note_uncertain(db, notification, outcome.error or "no_response", now)
        if notification.status == FAILED:
            report.failed += 1
        else:
            report.uncertain += 1
    elif outcome.kind == "refused":
        _note_failed(db, notification, outcome.error or "refused", now)
        report.failed += 1
    elif outcome.kind == "unconfigured":
        # Personne n'est en faute : on rend l'essai et on attend.
        notification.status = UNCERTAIN if notification.uncertain_count else PENDING
        notification.attempts -= 1
        notification.next_attempt_at = now + RETRY_DELAYS[0]
        notification.last_error = (outcome.error or "unconfigured")[:200]
        report.waiting += 1
    else:  # retry
        if notification.attempts >= MAX_ATTEMPTS:
            _note_failed(db, notification, outcome.error or "retry", now)
            report.failed += 1
            return
        delay = outcome.retry_after or RETRY_DELAYS[min(notification.attempts, len(RETRY_DELAYS)) - 1]
        notification.status = UNCERTAIN if notification.uncertain_count else PENDING
        notification.next_attempt_at = now + delay
        notification.last_error = (outcome.error or "retry")[:200]
        report.retried += 1


def send_due(db: Session | None = None, *, now: datetime | None = None, limit: int = BATCH_SIZE) -> Report:
    """Envoie les notifications dues des canaux configurés. Sûr à lancer en
    même temps depuis plusieurs processus (verrous de ligne). Ne lève pas pour
    une notification : une erreur inattendue de l'expéditeur la rend
    incertaine (on ne sait pas si la requête est partie)."""
    own = db is None
    db = db or database.SessionLocal()
    report = Report()
    clock = (lambda: now) if now is not None else _utcnow
    try:
        recover_interrupted(db, clock())
        channels = _ready_channels()
        if not channels:
            return report
        for notification_id, claimed_at in _claim(db, clock(), channels, limit):
            notification = db.get(Notification, notification_id)
            try:
                outcome = _TRANSPORTS[notification.channel].send(db, notification)
            except Exception as error:  # noqa: BLE001 - une ligne n'arrête jamais les autres
                logger.exception("Notification %s : erreur de l'expéditeur", notification_id)
                db.rollback()
                outcome = Outcome("uncertain", error=f"sender_error:{type(error).__name__}")
            notification = (
                db.query(Notification)
                .filter(Notification.id == notification_id)
                .with_for_update()
                .one()
            )
            if notification.status != SENDING or notification.claimed_at != claimed_at:
                # Reprise par un autre expéditeur entre-temps (envoi jugé
                # interrompu) : son état fait foi.
                db.commit()
                continue
            _apply(db, notification, outcome, clock(), report)
            db.commit()
        return report
    finally:
        if own:
            db.close()


def send_pending_in_background() -> None:
    """Envoi juste après une demande HTTP qui a créé des notifications. Ne
    lève jamais : la tâche planifiée `envoi-notifications` repasse chaque
    minute."""
    try:
        send_due()
    except Exception:  # noqa: BLE001
        logger.exception("Envoi des notifications après la demande : échec, la tâche planifiée reprendra")
