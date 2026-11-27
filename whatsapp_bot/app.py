"""Webhook Meta du service WhatsApp.

- `GET /webhook` : validation de l'adresse par Meta (une fois, à
  l'enregistrement) : `hub.verify_token` comparé en temps constant.
- `POST /webhook` : signature `X-Hub-Signature-256` vérifiée sur le corps
  brut, **avant** de lire le JSON ou de toucher à Redis ; sinon 401.

Chaque message est traité avant de répondre à Meta, une seule fois :

1. registre Redis (store.py) : un message déjà traité est écarté, un
   message en cours ailleurs répond 503 (Meta renverra) ;
2. verrou de la personne : ses messages sont traités dans l'ordre ;
3. réponse décidée avec le backend (conversation.py), envoyée, puis étape
   enregistrée et message noté « fait ». Un envoi refusé ou une panne au
   milieu : rien n'est noté, réponse 500, Meta renverra le webhook et le
   message sera repris depuis la même étape. Les écritures du backend
   portent le wamid : reprises, elles ne refont rien ;
4. backend injoignable : la personne reçoit « service indisponible,
   réessayez », et le message est noté « fait ». **Rien n'est rejoué plus
   tard à sa place** : c'est elle qui réessaie.
5. l'heure du message est notée au backend (fenêtre de 24 h des
   notifications) ; un échec ici ne fait jamais retraiter le message.

Statuts des notifications envoyées par le backend (reconnus à leur
`biz_opaque_callback_data`) et événements du compte (modèle refusé ou en
pause, qualité du numéro) : relayés au backend (`relay`) ; backend
injoignable = réponse 500, Meta renverra.

Journaux : identifiants de message et codes d'erreur seulement. Jamais le
texte d'un message, une position, un numéro, un secret ni une signature.
"""

from __future__ import annotations

import json
import logging
import secrets
from dataclasses import dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from messages import get_message
from whatsapp_bot import meta, signature
from whatsapp_bot.backend import BackendUnavailable, Refused
from whatsapp_bot.conversation import Conversation
from whatsapp_bot.store import Claim, Store

logger = logging.getLogger(__name__)

WEBHOOK_PATH = "/webhook"


@dataclass
class Service:
    app_secret: str
    verify_token: str
    phone_number_id: str
    store: Store
    messenger: meta.Messenger
    conversation: Conversation


class Busy(Exception):
    """Message en cours ailleurs, ou personne verrouillée : Meta renverra."""


async def process(service: Service, message: meta.Incoming) -> None:
    claim = await service.store.claim(message.message_id)
    if claim is Claim.DONE:
        return
    if claim is Claim.BUSY:
        raise Busy(message.message_id)
    token = secrets.token_hex(8)
    if not await service.store.lock(message.bsuid, token):
        await service.store.release(message.message_id)
        raise Busy(message.message_id)
    try:
        state = await service.store.conversation(message.bsuid)
        recipient = meta.Recipient(bsuid=message.bsuid, phone=message.phone)
        try:
            outcome = await service.conversation.handle(message, state)
        except BackendUnavailable as error:
            logger.warning("Message %s : backend indisponible (%s), la personne réessaiera", message.message_id, error)
            lang = state.get("language") if state.get("language") in ("fr", "ln", "en") else "fr"
            await service.messenger.send(recipient, meta.Text(get_message("service_unavailable", lang)))
            await service.store.complete(message.message_id)
            return
        except Refused as refusal:
            # Refus que la conversation n'attendait pas (identité refusée,
            # route fermée...) : la personne le sait, le message n'est pas
            # retraité en boucle.
            logger.error("Message %s : refus du backend non prévu (%s)", message.message_id, refusal.code)
            lang = state.get("language") if state.get("language") in ("fr", "ln", "en") else "fr"
            await service.messenger.send(recipient, meta.Text(get_message("wa_error", lang)))
            await service.store.complete(message.message_id)
            return
        for outgoing in outcome.messages:
            await service.messenger.send(recipient, outgoing)
        await service.store.save_conversation(message.bsuid, outcome.state)
        await service.store.complete(message.message_id)
    except BaseException:
        await service.store.release(message.message_id)
        raise
    finally:
        await service.store.unlock(message.bsuid, token)
    if message.timestamp is not None:
        try:
            await service.conversation.backend.seen(message.bsuid, message.message_id, message.timestamp)
        except (BackendUnavailable, Refused) as error:
            # Sans cette heure, une notification partira en modèle plutôt
            # qu'en message libre : jamais une raison de retraiter le message.
            logger.info("Message %s : heure de réception non notée (%s)", message.message_id, type(error).__name__)
    try:
        await service.messenger.mark_read(message.message_id)
    except meta.SendFailed as error:
        # Les deux coches bleues ne sont qu'un confort : jamais une raison de
        # retraiter le message.
        logger.info("Message %s : accusé de lecture non envoyé (%s)", message.message_id, error.reason)


async def relay(service: Service, batch: meta.Batch) -> bool:
    """Statuts des notifications et événements du compte, relayés au
    backend. Backend injoignable : False, Meta renverra le webhook (les
    messages déjà traités sont écartés, un statut relayé deux fois ne fait
    rien de plus). Refus du backend : journalisé, jamais rejoué en boucle."""
    backend = service.conversation.backend
    for status in batch.statuses:
        try:
            await backend.notification_status(status)
        except BackendUnavailable as error:
            logger.warning("Statut %s non relayé (%s), Meta renverra", status.message_id, error)
            return False
        except Refused as refusal:
            logger.error("Statut %s refusé par le backend (%s)", status.message_id, refusal.code)
    for event in batch.events:
        try:
            await backend.account_event(event)
        except BackendUnavailable as error:
            logger.warning("Événement %s non relayé (%s), Meta renverra", event.field, error)
            return False
        except Refused as refusal:
            logger.error("Événement %s refusé par le backend (%s)", event.field, refusal.code)
    return True


def build_app(service: Service) -> FastAPI:
    app = FastAPI(title="Nexis Hub — service WhatsApp", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get(WEBHOOK_PATH)
    async def verify(request: Request):
        params = request.query_params
        token = params.get("hub.verify_token") or ""
        if params.get("hub.mode") == "subscribe" and secrets.compare_digest(token.encode(), service.verify_token.encode()):
            return PlainTextResponse(params.get("hub.challenge") or "")
        return PlainTextResponse("Forbidden", status_code=403)

    @app.post(WEBHOOK_PATH)
    async def receive(request: Request):
        body = await request.body()
        if not signature.is_valid(service.app_secret, body, request.headers.get(signature.HEADER)):
            logger.warning("Webhook refusé : signature absente ou fausse")
            return PlainTextResponse("Unauthorized", status_code=401)
        try:
            payload = json.loads(body)
        except ValueError:
            return PlainTextResponse("Bad Request", status_code=400)
        batch = meta.parse_webhook(payload, service.phone_number_id)
        if batch.unidentified:
            logger.warning("Webhook : %s message(s) sans identifiant WhatsApp, ignoré(s)", batch.unidentified)
        for message in batch.messages:
            try:
                await process(service, message)
            except Busy:
                return PlainTextResponse("Busy", status_code=503)
            except meta.SendFailed as error:
                logger.error("Message %s : réponse non envoyée (%s), Meta renverra", message.message_id, error.reason)
                return PlainTextResponse("Retry", status_code=500)
            except Exception:
                logger.exception("Message %s : échec du traitement, Meta renverra", message.message_id)
                return PlainTextResponse("Retry", status_code=500)
        if not await relay(service, batch):
            return PlainTextResponse("Retry", status_code=500)
        return Response(status_code=200)

    @app.get("/health")
    @app.get("/health/live")
    async def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def ready():
        try:
            await service.store.ping()
        except Exception:
            return JSONResponse({"status": "indisponible", "problemes": ["redis injoignable"]}, status_code=503)
        return {"status": "ok"}

    return app
