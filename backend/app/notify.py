"""Expéditeur Telegram des notifications (backend/app/notifications.py).

Le backend n'écrit plus jamais directement à Telegram : chaque message passe
par la table `notifications`, écrite avec l'événement qui le cause. Ce module
ne fait qu'envoyer une notification déjà enregistrée et dire ce que Telegram
a répondu, sans jamais décider seul d'un renvoi :

- réponse `ok` : envoyée (identifiant du message gardé) ;
- connexion impossible avant l'envoi, trop de demandes (429), erreur de
  Telegram (5xx) : rien n'a été accepté, on pourra réessayer ;
- délai dépassé ou connexion coupée une fois la requête partie : incertaine ;
- refus de Telegram (400, 403 : personne qui a bloqué le bot, conversation
  inconnue) : échec définitif ;
- jeton absent ou refusé (401, 404) : expéditeur non configuré, la
  notification attend.

Les appels sont synchrones (`httpx`) : l'expéditeur tourne dans la tâche
planifiée et juste après les demandes HTTP du backend, jamais dans la boucle
asyncio du bot.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from backend.app import notifications
from backend.app.models import ChannelIdentity, Notification

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TIMEOUT = httpx.Timeout(10.0, connect=5.0)
# Limites de Telegram.
MAX_TEXT = 4096
MAX_CAPTION = 1024

logger = logging.getLogger("nexis.notifications.telegram")


def reply_markup(buttons: list[list[tuple[str, str]]]) -> dict | None:
    if not buttons:
        return None
    return {"inline_keyboard": [[{"text": label, "callback_data": action} for label, action in row] for row in buttons]}


class TelegramTransport:
    channel = notifications.TELEGRAM

    def configured(self) -> bool:
        return bool(BOT_TOKEN)

    def _chat_id(self, db: Session, account_id: int) -> str | None:
        row = (
            db.query(ChannelIdentity.external_id)
            .filter(ChannelIdentity.account_id == account_id, ChannelIdentity.channel == notifications.TELEGRAM)
            .one_or_none()
        )
        return row[0] if row else None

    def send(self, db: Session, notification: Notification) -> notifications.Outcome:
        chat_id = self._chat_id(db, notification.recipient_account_id)
        if chat_id is None:
            return notifications.Outcome("refused", error="telegram_identity_missing")
        rendered = notifications.render(db, notification)
        markup = reply_markup(rendered.buttons)
        media = rendered.media
        if media is not None and media["channel"] != notifications.TELEGRAM:
            if not media.get("optional"):
                return notifications.Outcome("refused", error="media_other_channel")
            media = None
        if media is None:
            return self._call("sendMessage", {"chat_id": chat_id, "text": rendered.text[:MAX_TEXT]}, markup)
        if media["kind"] == "video_note":
            # Une note vidéo ne porte pas de texte : le numéro de mission part
            # dans la notification suivante.
            return self._call("sendVideoNote", {"chat_id": chat_id, "video_note": media["id"]}, markup, parse=False)
        method, field = ("sendPhoto", "photo") if media["kind"] == "photo" else ("sendVoice", "voice")
        if len(rendered.text) > MAX_CAPTION:
            return notifications.Outcome("refused", error="caption_too_long")
        outcome = self._call(method, {"chat_id": chat_id, field: media["id"], "caption": rendered.text}, markup)
        if outcome.kind == "refused" and media.get("optional"):
            # Photo refusée (fichier plus valable) : le texte part quand même.
            return self._call("sendMessage", {"chat_id": chat_id, "text": rendered.text[:MAX_TEXT]}, markup)
        return outcome

    def _call(self, method: str, content: dict, markup: dict | None, *, parse: bool = True) -> notifications.Outcome:
        payload = dict(content)
        if parse:
            payload["parse_mode"] = "HTML"
        if markup:
            payload["reply_markup"] = markup
        try:
            response = httpx.post(f"https://api.telegram.org/bot{BOT_TOKEN}/{method}", json=payload, timeout=TIMEOUT)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.PoolTimeout) as error:
            # La requête n'est jamais partie : réessayer est sûr.
            return notifications.Outcome("retry", error=f"connect:{type(error).__name__}")
        except httpx.HTTPError as error:
            # Partie, réponse perdue : peut-être reçue.
            return notifications.Outcome("uncertain", error=f"transport:{type(error).__name__}")
        return _outcome(response)


def _outcome(response: httpx.Response) -> notifications.Outcome:
    try:
        body = response.json()
    except ValueError:
        body = {}
    description = str(body.get("description") or "")[:150] if isinstance(body, dict) else ""
    status = response.status_code
    if status == 200 and isinstance(body, dict) and body.get("ok"):
        result = body.get("result") or {}
        message_id = result.get("message_id") if isinstance(result, dict) else None
        return notifications.Outcome("sent", message_id=str(message_id) if message_id is not None else None)
    if status == 200:
        return notifications.Outcome("uncertain", error="telegram_unreadable_answer")
    if status == 429:
        retry_after = (body.get("parameters") or {}).get("retry_after") if isinstance(body, dict) else None
        delay = timedelta(seconds=int(retry_after)) if isinstance(retry_after, int) and retry_after > 0 else None
        return notifications.Outcome("retry", error="telegram_429", retry_after=delay)
    if status in (401, 404):
        logger.error("Telegram refuse le jeton du bot (%s) : notifications en attente", status)
        return notifications.Outcome("unconfigured", error=f"telegram_{status}")
    if status >= 500:
        return notifications.Outcome("retry", error=f"telegram_{status}")
    return notifications.Outcome("refused", error=f"telegram_{status}:{description}")


notifications.register_transport(TelegramTransport())
