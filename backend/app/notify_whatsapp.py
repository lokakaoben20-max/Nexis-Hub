"""Expéditeur WhatsApp des notifications (étape 8 du plan WhatsApp).

Comme l'expéditeur Telegram (backend/app/notify.py), ce module ne fait
qu'envoyer une notification déjà enregistrée dans la table `notifications`
et dire ce que Meta a répondu. Il appelle directement l'API WhatsApp Cloud de
Meta (même jeton que le service WhatsApp).

Fenêtre de 24 h
---------------
Meta ne laisse écrire librement que dans les 24 h qui suivent le dernier
message de la personne (`channel_identities.last_inbound_at`, noté par le
service WhatsApp à chaque message reçu). Avec une marge (`WINDOW`) :

- dans la fenêtre : le texte complet de la notification, avec ses boutons,
  au format WhatsApp ;
- hors fenêtre, ou si Meta a déjà refusé le message libre
  (`template_required`) : le modèle validé `nexis_suivi`
  (backend/app/modeles_whatsapp.py), avec un bouton qui ouvre la demande.

Si Meta refuse quand même le message libre (erreur 131047, souvent annoncée
plus tard par un statut), rien n'est arrivé : la notification repart en
modèle (`notifications.require_template`).

Statuts de Meta
---------------
Chaque envoi porte `biz_opaque_callback_data` = `nexis:<notification>:<essai>`.
Meta le renvoie dans ses webhooks de statut, que le service WhatsApp relaie
(`apply_status`) : un statut `sent` ou `delivered` règle un envoi incertain
sans renvoi ; un statut `failed` arrivé après coup passe la notification en
échec (alerte admin), ou la renvoie en modèle si la fenêtre était fermée.
Le numéro d'essai écarte le statut tardif d'un ancien envoi.

Réponses de l'API, sans jamais décider seul d'un renvoi :

- wamid rendu : envoyée ;
- connexion impossible avant l'envoi, trop de demandes : on pourra réessayer ;
- délai dépassé, connexion coupée, erreur 5xx de Meta : incertaine ;
- jeton refusé, modèle absent, en pause ou désactivé : non configuré, la
  notification attend (l'admin est prévenu par le webhook de modèle) ;
- autre refus (numéro qui n'a pas WhatsApp...) : échec définitif.

Aucun texte de message n'est écrit dans les journaux.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import json
import logging
import os
import re
from datetime import datetime, timedelta

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.app import modeles_whatsapp, notifications
from backend.app.models import ChannelIdentity, NexisAccount, Notification
from messages import get_message

load_dotenv()

DEFAULT_GRAPH_URL = "https://graph.facebook.com/v23.0"
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Meta ferme la fenêtre 24 h après le dernier message reçu : on garde une
# marge pour les horloges et le temps d'envoi.
WINDOW = timedelta(hours=23)

# Limites de WhatsApp (mêmes valeurs que whatsapp_bot/meta.py).
MAX_TEXT = 4096
MAX_INTERACTIVE_BODY = 1024
MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20
MAX_LIST_ROWS = 10
MAX_ROW_TITLE = 24

# Boutons que le service WhatsApp sait traiter (whatsapp_bot/devis.py,
# suivi.py, litige.py, conversation.py ; vérifié par
# whatsapp_bot/tests/test_whatsapp_notifications_service.py). Un autre bouton (action
# de Telegram seulement) n'est pas montré : la personne retrouve tout par le menu.
WHATSAPP_ACTIONS = (
    "quote_accept_",
    "quote_reject_",
    "client_confirm_done_",
    "client_report_issue_",
    "presence_yes_",
    "presence_notyet_",
    "presence_wrong_",
    "dispute_contest_c_",
    "doffer_new_",
    "mis:",
    "menu:",
)

CALLBACK_PREFIX = "nexis"
_CALLBACK = re.compile(rf"{CALLBACK_PREFIX}:(\d{{1,12}}):(\d{{1,4}}):([0-9a-f]{{32}})")
MIN_CALLBACK_KEY = 32

# Codes d'erreur de Meta.
WINDOW_CLOSED_CODES = {131047, 470}
RATE_LIMIT_CODES = {4, 80007, 130429, 131048, 131056}
UNCONFIGURED_CODES = {190, 10, 200, 133010}  # jeton, droits, numéro non enregistré
# 132xxx : modèle absent, en pause, désactivé, paramètres refusés.

logger = logging.getLogger("nexis.notifications.whatsapp")


def _setting(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _http_post(url: str, **kwargs) -> httpx.Response:
    """Seul appel réseau du module (remplacé par le faux Meta dans les tests)."""
    return httpx.post(url, **kwargs)


# --- Format WhatsApp ------------------------------------------------------------------

_TAGS = ((re.compile(r"</?(b|strong)>"), "*"), (re.compile(r"</?(i|em)>"), "_"), (re.compile(r"</?(s|strike|del)>"), "~"))
_CODE = re.compile(r"</?code>")
_ANY_TAG = re.compile(r"<[^>]+>")


def whatsapp_text(telegram_html: str) -> str:
    """Texte HTML de Telegram (valeurs déjà échappées) → texte WhatsApp :
    gras, italique, barré convertis ; autres balises retirées ; entités
    rendues. Les valeurs écrites par une personne sont échappées avant :
    elles ne contiennent jamais de balise."""
    text = telegram_html
    for pattern, mark in _TAGS:
        text = pattern.sub(mark, text)
    text = _CODE.sub("```", text)
    text = _ANY_TAG.sub("", text)
    return html.unescape(text).strip()


def _short(label: str, limit: int) -> str:
    label = " ".join(label.split())
    return label if len(label) <= limit else label[: limit - 1].rstrip() + "…"


def _shown_buttons(buttons: list[list[tuple[str, str]]]) -> list[tuple[str, str]]:
    return [(action, label) for row in buttons for label, action in row if action.startswith(WHATSAPP_ACTIONS)]


def free_message(rendered: notifications.Rendered, lang: str) -> dict:
    """Message libre (fenêtre ouverte) : texte, boutons ou liste."""
    body = whatsapp_text(rendered.text)
    buttons = _shown_buttons(rendered.buttons)
    if buttons and len(body) > MAX_INTERACTIVE_BODY:
        # Texte trop long pour porter des boutons : le texte d'abord ; la
        # demande reste ouvrable par « Mes demandes ».
        logger.warning("Notification WhatsApp trop longue pour ses boutons : envoyée sans boutons")
        buttons = []
    if not buttons:
        return {"type": "text", "text": {"body": body[:MAX_TEXT], "preview_url": False}}
    if len(buttons) <= MAX_BUTTONS:
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": body},
                "action": {
                    "buttons": [
                        {"type": "reply", "reply": {"id": action, "title": _short(label, MAX_BUTTON_TITLE)}}
                        for action, label in buttons
                    ]
                },
            },
        }
    rows = [{"id": action, "title": _short(label, MAX_ROW_TITLE)} for action, label in buttons[:MAX_LIST_ROWS]]
    button = get_message("wa_list_offer", lang)
    return {
        "type": "interactive",
        "interactive": {
            "type": "list",
            "body": {"text": body},
            "action": {"button": button, "sections": [{"title": button, "rows": rows}]},
        },
    }


def template_message(notification: Notification, lang: str) -> dict:
    params = notification.params or {}
    return {
        "type": "template",
        "template": {
            "name": modeles_whatsapp.TEMPLATE_NAME,
            "language": {"code": modeles_whatsapp.template_language(lang)},
            "components": modeles_whatsapp.components(notification.message_key, params, lang),
        },
    }


def _callback_key() -> bytes | None:
    """Clé du backend seul (`WHATSAPP_CALLBACK_KEY`), jamais donnée au service
    WhatsApp : un statut relayé ne peut viser que l'envoi qui le porte."""
    key = _setting("WHATSAPP_CALLBACK_KEY")
    return key.encode() if len(key) >= MIN_CALLBACK_KEY else None


def _callback_mac(key: bytes, notification_id: int, attempt: int) -> str:
    return hmac.new(key, f"{notification_id}:{attempt}".encode(), hashlib.sha256).hexdigest()[:32]


def callback_data(notification: Notification) -> str:
    """`nexis:<notification>:<essai>:<signature>`. Sans clé, l'expéditeur
    n'est pas configuré : aucun envoi ne part sans signature."""
    key = _callback_key()
    mac = _callback_mac(key, notification.id, notification.attempts) if key else ""
    return f"{CALLBACK_PREFIX}:{notification.id}:{notification.attempts}:{mac}"


def window_open(last_inbound_at: datetime | None, now: datetime) -> bool:
    return last_inbound_at is not None and now - last_inbound_at < WINDOW


# --- Envoi -----------------------------------------------------------------------------


class WhatsAppTransport:
    channel = notifications.WHATSAPP

    def configured(self) -> bool:
        return bool(_setting("WHATSAPP_ACCESS_TOKEN") and _setting("WHATSAPP_PHONE_NUMBER_ID") and _callback_key())

    def send(self, db: Session, notification: Notification) -> notifications.Outcome:
        identity = (
            db.query(ChannelIdentity)
            .filter(
                ChannelIdentity.account_id == notification.recipient_account_id,
                ChannelIdentity.channel == notifications.WHATSAPP,
            )
            .one_or_none()
        )
        if identity is None:
            return notifications.Outcome("refused", error="whatsapp_identity_missing")
        account = db.get(NexisAccount, notification.recipient_account_id)
        lang = notifications.language_of(db, notification.recipient_account_id)
        now = notifications._utcnow()
        use_template = notification.template_required or not window_open(identity.last_inbound_at, now)
        if use_template:
            content = template_message(notification, lang)
        else:
            rendered = notifications.render(db, notification, lang)
            media = rendered.media
            if media is not None and media.get("channel") != notifications.WHATSAPP and not media.get("optional"):
                return notifications.Outcome("refused", error="media_other_channel")
            content = free_message(rendered, lang)
        # Numéro prouvé par WhatsApp à l'inscription quand Meta l'a donné,
        # sinon l'identifiant WhatsApp de la personne (BSUID).
        address = {"to": account.phone_e164.lstrip("+")} if account is not None and account.phone_e164 else {"recipient": identity.external_id}
        body = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            **address,
            **content,
            "biz_opaque_callback_data": callback_data(notification),
        }
        return self._post(body, template=use_template)

    def _post(self, body: dict, *, template: bool) -> notifications.Outcome:
        url = f"{_setting('WHATSAPP_GRAPH_URL', DEFAULT_GRAPH_URL).rstrip('/')}/{_setting('WHATSAPP_PHONE_NUMBER_ID')}/messages"
        headers = {"Authorization": f"Bearer {_setting('WHATSAPP_ACCESS_TOKEN')}"}
        try:
            response = _http_post(url, json=body, headers=headers, timeout=TIMEOUT)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as error:
            return notifications.Outcome("retry", error=f"connect:{type(error).__name__}")
        except httpx.HTTPError as error:
            return notifications.Outcome("uncertain", error=f"transport:{type(error).__name__}")
        return _outcome(response, template=template)


def _error_code(answer) -> int | None:
    error = answer.get("error") if isinstance(answer, dict) else None
    code = error.get("code") if isinstance(error, dict) else None
    return code if isinstance(code, int) else None


def _outcome(response: httpx.Response, *, template: bool) -> notifications.Outcome:
    try:
        answer = response.json()
    except ValueError:
        answer = {}
    status = response.status_code
    if status == 200:
        try:
            return notifications.Outcome("sent", message_id=str(answer["messages"][0]["id"]))
        except (KeyError, IndexError, TypeError):
            return notifications.Outcome("uncertain", error="whatsapp_unreadable_answer")
    if status >= 500:
        # Meta a peut-être pris le message : un statut le dira.
        return notifications.Outcome("uncertain", error=f"whatsapp_{status}")
    code = _error_code(answer)
    error = f"whatsapp_{status}:{code}"
    if code in WINDOW_CLOSED_CODES and not template:
        return notifications.Outcome("needs_template", error=error)
    if status == 429 or code in RATE_LIMIT_CODES:
        return notifications.Outcome("retry", error=error)
    if status == 401 or code in UNCONFIGURED_CODES or (code is not None and 132000 <= code < 133000):
        logger.error("Meta refuse l'envoi WhatsApp (%s) : notifications en attente", error)
        return notifications.Outcome("unconfigured", error=error)
    return notifications.Outcome("refused", error=error)


# --- Code de connexion de l'app ------------------------------------------------------


def send_login_code(bsuid: str, code: str, lang: str) -> notifications.Outcome:
    """Code de connexion de l'app, en réponse au message que la personne
    vient d'envoyer depuis le lien de l'app (fenêtre ouverte : message libre,
    sans modèle). Envoyé par le backend, hors de la table `notifications` et
    hors de la réponse rendue au service : le code n'est écrit nulle part en
    clair, ni en base ni dans un journal. Il part à l'identité WhatsApp
    (BSUID) qui vient d'écrire, jamais à un numéro."""

    body = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "recipient": bsuid,
        "type": "text",
        "text": {"body": whatsapp_text(get_message("app_login_code", lang, code=code)), "preview_url": False},
    }
    return WhatsAppTransport()._post(body, template=False)


# --- Statuts relayés par le service WhatsApp -------------------------------------------


def parse_callback(value: str | None) -> tuple[int, int] | None:
    """(notification, essai) d'un statut, seulement si la signature est
    celle du backend : un statut forgé ne touche à rien."""
    match = _CALLBACK.fullmatch(value or "")
    key = _callback_key()
    if match is None or key is None:
        return None
    notification_id, attempt = int(match.group(1)), int(match.group(2))
    if not hmac.compare_digest(match.group(3), _callback_mac(key, notification_id, attempt)):
        return None
    return notification_id, attempt


def apply_status(db: Session, *, callback: str, message_id: str, status: str, error_code: int | None, now: datetime) -> str:
    """Statut d'un message envoyé par ce module. Rend ce qui a été fait :
    `confirmed`, `template`, `failed` ou `ignored` (statut d'un ancien essai,
    déjà connu, ou d'une notification inconnue). Ne valide pas."""
    parsed = parse_callback(callback)
    if parsed is None:
        return "ignored"
    notification_id, attempt = parsed
    notification = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.channel == notifications.WHATSAPP)
        .with_for_update()
        .one_or_none()
    )
    if notification is None or notification.attempts != attempt:
        return "ignored"
    if notification.provider_message_id and notification.provider_message_id != message_id:
        return "ignored"
    if status in ("sent", "delivered", "read"):
        return "confirmed" if notifications.confirm_delivery(db, notification, message_id, now) else "ignored"
    if status == "failed":
        window_closed = error_code in WINDOW_CLOSED_CODES
        error = f"whatsapp_status:{error_code}"
        if not notifications.delivery_failed(db, notification, error, now, window_closed=window_closed):
            return "ignored"
        return "template" if notification.status == notifications.PENDING else "failed"
    return "ignored"


# --- Événements du compte WhatsApp (relayés par le service) --------------------------

META_EVENT_FIELDS = (
    "message_template_status_update",
    "message_template_quality_update",
    "template_category_update",
    "phone_number_quality_update",
    "account_update",
    "account_alerts",
    "business_capability_update",
)
_TEMPLATE_EVENTS = {
    "APPROVED": "approuvé ✅",
    "REJECTED": "refusé ❌",
    "PAUSED": "mis en pause ⏸️",
    "DISABLED": "désactivé ❌",
    "FLAGGED": "signalé par Meta (qualité basse) ⚠️",
    "REINSTATED": "rétabli ✅",
    "PENDING_DELETION": "en cours de suppression",
    "IN_APPEAL": "en appel",
    "PENDING": "en attente d'examen",
}
_TEMPLATE_USABLE = {"APPROVED", "REINSTATED", "PENDING", "IN_APPEAL"}


def _clip(value, limit: int = 200) -> str:
    return html.escape(" ".join(str(value if value is not None else "—").split())[:limit])


def meta_event_text(field: str, value: dict) -> str:
    """Alerte (HTML déjà échappé) pour l'équipe."""
    if field == "message_template_status_update":
        event = str(value.get("event") or "")
        text = (
            f"📋 Modèle WhatsApp « {_clip(value.get('message_template_name'))} » "
            f"({_clip(value.get('message_template_language'))}) : {_TEMPLATE_EVENTS.get(event, _clip(event))}."
        )
        reason = value.get("reason")
        if reason and reason != "NONE":
            text += f"\nRaison donnée par Meta : {_clip(reason)}."
        if event not in _TEMPLATE_USABLE:
            text += (
                "\nLes notifications hors de la fenêtre de 24 h attendent tant qu'il n'est pas approuvé. "
                "Dans la fenêtre, le message libre continue."
            )
        return text
    if field == "phone_number_quality_update":
        limit = value.get("current_limit") or value.get("messaging_limit_tier")
        return (
            f"📶 Numéro WhatsApp {_clip(value.get('display_phone_number'))} : {_clip(value.get('event'))}"
            f" (limite d'envoi : {_clip(limit)})."
        )
    details = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return f"🚨 Compte WhatsApp chez Meta ({_clip(field)}) : {_clip(details, 600)}"


def alert_meta_event(db: Session, field: str, value: dict, *, sent_at: int | None, now: datetime) -> int:
    """Une alerte par événement : clé tirée du contenu et de l'heure donnée par
    Meta (`entry.time`). Le même webhook relayé deux fois n'en crée qu'une ;
    le même événement plus tard (modèle remis en pause) en crée une autre.
    Ne valide pas."""
    canonical = json.dumps({"field": field, "value": value, "time": sent_at}, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:32]
    if field == "message_template_status_update" and str(value.get("event") or "") not in _TEMPLATE_USABLE:
        event = str(value.get("event") or "")
        logger.error(
            "Modèle WhatsApp inutilisable (%s) : notifications hors fenêtre en attente",
            event if event in _TEMPLATE_EVENTS else "événement inconnu",
        )
    return notifications.enqueue_admins(
        db, event_key=f"whatsapp_meta:{digest}", params=notifications.admin_text(meta_event_text(field, value)), now=now
    )


notifications.register_transport(WhatsAppTransport())
