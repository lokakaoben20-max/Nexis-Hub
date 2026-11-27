"""Tout ce qui parle le format de Meta : lecture des webhooks, envoi.

Le reste du service ne voit que `Incoming` (un message reçu, déjà trié) et
les messages sortants (`Text`, `Buttons`, `Menu`, `LocationRequest`,
`Template`), envoyés par
un `Messenger`. Changer de fournisseur ne toucherait que ce fichier.

Identité : depuis 2026, Meta identifie chaque personne par un identifiant
propre à l'entreprise (BSUID, `user_id` / `from_user_id`) et peut masquer
son numéro (`wa_id` / `from` absents). Le BSUID est l'identité du compte ;
le numéro, quand Meta le donne, est un numéro prouvé par WhatsApp.

Limites de WhatsApp vérifiées ici avant tout envoi (et par le faux serveur
Meta) : 3 boutons de 20 caractères au plus, listes de 10 lignes (titre de
24 caractères, description de 72), texte d'un message interactif de 1 024
caractères, message texte de 4 096.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

MAX_BUTTONS = 3
MAX_BUTTON_TITLE = 20
MAX_LIST_ROWS = 10
MAX_ROW_TITLE = 24
MAX_ROW_DESCRIPTION = 72
MAX_INTERACTIVE_BODY = 1024
MAX_TEXT_BODY = 4096
MAX_ID = 200

# Types de message reçus.
TEXT = "text"
CHOICE = "choice"  # bouton de réponse, ligne de liste, bouton de modèle
LOCATION = "location"
MEDIA = "media"  # photo, vocal, vidéo, document, autocollant, contact...
IGNORED = "ignored"  # réaction, message système, type inconnu sans réponse utile

_MEDIA_TYPES = {"image", "audio", "video", "document", "sticker", "contacts", "unsupported"}
_IGNORED_TYPES = {"reaction", "system", "request_welcome", "ephemeral", "order"}


@dataclass(frozen=True)
class Incoming:
    """Un message reçu. `message_id` (wamid) sert de clé d'idempotence."""

    message_id: str
    bsuid: str
    phone: str | None  # E.164 avec « + », seulement si Meta l'a donné
    kind: str
    text: str | None = None
    choice: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Heure du message chez Meta (secondes UTC) : ouvre la fenêtre de 24 h.
    timestamp: int | None = None


# Statuts d'envoi relayés au backend : ceux des notifications qu'il a
# envoyées, reconnues à leur `biz_opaque_callback_data`
# (backend/app/notify_whatsapp.py). `read` n'apprend rien de plus que
# `delivered`.
NOTIFICATION_CALLBACK_PREFIX = "nexis:"
RELAYED_STATUSES = ("sent", "delivered", "failed")
# Événements du compte relayés à l'équipe (backend/app/notify_whatsapp.py,
# META_EVENT_FIELDS).
ACCOUNT_EVENT_FIELDS = (
    "message_template_status_update",
    "message_template_quality_update",
    "template_category_update",
    "phone_number_quality_update",
    "account_update",
    "account_alerts",
    "business_capability_update",
)


@dataclass(frozen=True)
class Status:
    """Statut d'un message envoyé par l'expéditeur de notifications."""

    message_id: str
    status: str
    callback: str
    error_code: int | None = None


@dataclass(frozen=True)
class AccountEvent:
    field: str
    value: dict


@dataclass(frozen=True)
class Batch:
    """Ce qu'un webhook contient pour notre numéro."""

    messages: list[Incoming] = field(default_factory=list)
    statuses: list[Status] = field(default_factory=list)
    events: list[AccountEvent] = field(default_factory=list)
    # Messages sans identité exploitable (aucun BSUID) : comptés, jamais traités.
    unidentified: int = 0


def _phone(value) -> str | None:
    digits = str(value or "").strip().lstrip("+")
    return f"+{digits}" if digits.isdigit() and 8 <= len(digits) <= 15 else None


def parse_webhook(payload: dict, phone_number_id: str) -> Batch:
    """Messages adressés à notre numéro, dans l'ordre, statuts des
    notifications et événements du compte. Ce qui vient d'un autre numéro de
    l'entreprise ou d'un autre type de compte est ignoré."""
    messages: list[Incoming] = []
    statuses: list[Status] = []
    events: list[AccountEvent] = []
    unidentified = 0
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        return Batch()
    for entry in payload.get("entry") or []:
        for change in (entry or {}).get("changes") or []:
            name = (change or {}).get("field")
            value = (change or {}).get("value") or {}
            if not isinstance(value, dict):
                continue
            if name in ACCOUNT_EVENT_FIELDS:
                events.append(AccountEvent(field=name, value=value))
                continue
            if name != "messages":
                continue
            if str((value.get("metadata") or {}).get("phone_number_id")) != str(phone_number_id):
                continue
            for raw in value.get("statuses") or []:
                status = _status(raw)
                if status is not None:
                    statuses.append(status)
            contacts = value.get("contacts") or []
            for raw in value.get("messages") or []:
                incoming = _message(raw, contacts)
                if incoming is None:
                    unidentified += 1
                else:
                    messages.append(incoming)
    return Batch(messages=messages, statuses=statuses, events=events, unidentified=unidentified)


def _status(raw) -> Status | None:
    if not isinstance(raw, dict):
        return None
    callback = str(raw.get("biz_opaque_callback_data") or "")
    status = raw.get("status")
    message_id = str(raw.get("id") or "")
    if not callback.startswith(NOTIFICATION_CALLBACK_PREFIX) or status not in RELAYED_STATUSES or not message_id:
        return None
    code = None
    for error in raw.get("errors") or []:
        if isinstance(error, dict) and isinstance(error.get("code"), int):
            code = error["code"]
            break
    return Status(message_id=message_id[:200], status=status, callback=callback[:512], error_code=code)


def _contact_for(raw: dict, contacts: list) -> dict:
    for contact in contacts:
        if not isinstance(contact, dict):
            continue
        if raw.get("from_user_id") and contact.get("user_id") == raw.get("from_user_id"):
            return contact
        if raw.get("from") and contact.get("wa_id") == raw.get("from"):
            return contact
    return contacts[0] if len(contacts) == 1 and isinstance(contacts[0], dict) else {}


def _message(raw: dict, contacts: list) -> Incoming | None:
    if not isinstance(raw, dict):
        return None
    message_id = str(raw.get("id") or "")
    contact = _contact_for(raw, contacts)
    bsuid = str(raw.get("from_user_id") or contact.get("user_id") or "")
    if not message_id or not bsuid:
        return None
    phone = _phone(raw.get("from") or contact.get("wa_id"))
    kind = raw.get("type")
    stamp = str(raw.get("timestamp") or "")
    base = {"message_id": message_id, "bsuid": bsuid, "phone": phone, "timestamp": int(stamp) if stamp.isdigit() else None}
    if kind == "text":
        return Incoming(kind=TEXT, text=str((raw.get("text") or {}).get("body") or ""), **base)
    if kind == "interactive":
        interactive = raw.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        if reply.get("id"):
            return Incoming(kind=CHOICE, choice=str(reply["id"]), **base)
        return Incoming(kind=IGNORED, **base)
    if kind == "button":  # bouton d'un modèle (étape 8)
        payload = (raw.get("button") or {}).get("payload")
        return Incoming(kind=CHOICE, choice=str(payload), **base) if payload else Incoming(kind=IGNORED, **base)
    if kind == "location":
        location = raw.get("location") or {}
        try:
            latitude, longitude = float(location["latitude"]), float(location["longitude"])
        except (KeyError, TypeError, ValueError):
            return Incoming(kind=IGNORED, **base)
        return Incoming(kind=LOCATION, latitude=latitude, longitude=longitude, **base)
    if kind in _IGNORED_TYPES:
        return Incoming(kind=IGNORED, **base)
    if kind in _MEDIA_TYPES:
        return Incoming(kind=MEDIA, **base)
    return Incoming(kind=MEDIA, **base)


# --- Messages sortants -------------------------------------------------------------


def _check(condition: bool, what: str) -> None:
    if not condition:
        raise ValueError(f"Message WhatsApp refusé avant envoi : {what}")


@dataclass(frozen=True)
class Text:
    body: str

    def payload(self) -> dict:
        _check(0 < len(self.body) <= MAX_TEXT_BODY, "texte vide ou trop long")
        return {"type": "text", "text": {"body": self.body, "preview_url": True}}


@dataclass(frozen=True)
class Buttons:
    """Jusqu'à 3 boutons de réponse : (identifiant, libellé)."""

    body: str
    buttons: tuple[tuple[str, str], ...]

    def payload(self) -> dict:
        _check(0 < len(self.body) <= MAX_INTERACTIVE_BODY, "texte de boutons vide ou trop long")
        _check(0 < len(self.buttons) <= MAX_BUTTONS, "nombre de boutons")
        for button_id, title in self.buttons:
            _check(0 < len(button_id) <= MAX_ID, "identifiant de bouton")
            _check(0 < len(title) <= MAX_BUTTON_TITLE, f"libellé de bouton trop long : {title!r}")
        return {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": self.body},
                "action": {
                    "buttons": [{"type": "reply", "reply": {"id": button_id, "title": title}} for button_id, title in self.buttons]
                },
            },
        }


@dataclass(frozen=True)
class Menu:
    """Liste de 10 lignes au plus : (identifiant, titre, description)."""

    body: str
    button: str
    rows: tuple[tuple[str, str, str], ...]

    def payload(self) -> dict:
        _check(0 < len(self.body) <= MAX_INTERACTIVE_BODY, "texte de liste vide ou trop long")
        _check(0 < len(self.button) <= MAX_BUTTON_TITLE, f"bouton de liste trop long : {self.button!r}")
        _check(0 < len(self.rows) <= MAX_LIST_ROWS, "nombre de lignes")
        for row_id, title, description in self.rows:
            _check(0 < len(row_id) <= MAX_ID, "identifiant de ligne")
            _check(0 < len(title) <= MAX_ROW_TITLE, f"titre de ligne trop long : {title!r}")
            _check(len(description) <= MAX_ROW_DESCRIPTION, f"description trop longue : {description!r}")
        rows = [
            {"id": row_id, "title": title, **({"description": description} if description else {})}
            for row_id, title, description in self.rows
        ]
        return {
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": self.body},
                "action": {"button": self.button, "sections": [{"title": self.button, "rows": rows}]},
            },
        }


@dataclass(frozen=True)
class LocationRequest:
    """Message avec le bouton « Envoyer la position » de WhatsApp : la
    réponse est un message de type `location`."""

    body: str

    def payload(self) -> dict:
        _check(0 < len(self.body) <= MAX_INTERACTIVE_BODY, "texte de demande de position vide ou trop long")
        return {
            "type": "interactive",
            "interactive": {
                "type": "location_request_message",
                "body": {"text": self.body},
                "action": {"name": "send_location"},
            },
        }


@dataclass(frozen=True)
class Template:
    """Modèle validé par Meta (hors fenêtre de 24 h). Utilisé à l'étape 8."""

    name: str
    language: str
    parameters: tuple[str, ...] = ()

    def payload(self) -> dict:
        _check(bool(self.name) and bool(self.language), "modèle sans nom ou sans langue")
        template = {"name": self.name, "language": {"code": self.language}}
        if self.parameters:
            template["components"] = [
                {"type": "body", "parameters": [{"type": "text", "text": value} for value in self.parameters]}
            ]
        return {"type": "template", "template": template}


Outgoing = Text | Buttons | Menu | LocationRequest | Template


# --- Envoi ---------------------------------------------------------------------------


class SendFailed(Exception):
    """Meta n'a pas accepté le message, ou n'a pas répondu. `uncertain` :
    la demande est peut-être arrivée (réponse perdue)."""

    def __init__(self, reason: str, *, uncertain: bool = False):
        super().__init__(reason)
        self.reason = reason
        self.uncertain = uncertain


@dataclass(frozen=True)
class Recipient:
    """À qui écrire : le numéro quand Meta l'a donné, sinon le BSUID."""

    bsuid: str
    phone: str | None = None

    def address(self) -> dict:
        if self.phone:
            return {"to": self.phone.lstrip("+")}
        return {"recipient": self.bsuid}


class Messenger:
    """Interface d'envoi. `CloudApi` est l'implémentation Meta."""

    async def send(self, recipient: Recipient, message: Outgoing) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    async def mark_read(self, message_id: str) -> None:  # pragma: no cover - interface
        raise NotImplementedError


class CloudApi(Messenger):
    """API WhatsApp Cloud de Meta, en direct. `transport` : pour les tests
    (faux serveur Meta dans le même processus)."""

    def __init__(self, graph_url: str, phone_number_id: str, access_token: str, *, transport=None, timeout: float = 10.0):
        self._url = f"{graph_url.rstrip('/')}/{phone_number_id}/messages"
        self._headers = {"Authorization": f"Bearer {access_token}"}
        self._transport = transport
        self._timeout = timeout

    async def _post(self, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(self._url, json=body, headers=self._headers)
        except (httpx.ConnectError, httpx.ConnectTimeout) as error:
            # Rien n'est parti.
            raise SendFailed(f"transport:{type(error).__name__}") from error
        except httpx.HTTPError as error:
            # Partie, réponse perdue : peut-être reçue par Meta.
            raise SendFailed(f"transport:{type(error).__name__}", uncertain=True) from error
        try:
            answer = response.json()
        except ValueError:
            answer = {}
        if response.status_code >= 500:
            raise SendFailed(f"meta_{response.status_code}", uncertain=True)
        if response.status_code != 200:
            code = ((answer.get("error") or {}) if isinstance(answer, dict) else {}).get("code")
            raise SendFailed(f"meta_{response.status_code}:{code}")
        return answer if isinstance(answer, dict) else {}

    async def send(self, recipient: Recipient, message: Outgoing) -> str:
        body = {"messaging_product": "whatsapp", "recipient_type": "individual", **recipient.address(), **message.payload()}
        answer = await self._post(body)
        try:
            return str(answer["messages"][0]["id"])
        except (KeyError, IndexError, TypeError) as error:
            raise SendFailed("meta_unexpected_answer", uncertain=True) from error

    async def mark_read(self, message_id: str) -> None:
        await self._post({"messaging_product": "whatsapp", "status": "read", "message_id": message_id})
