"""Faux serveur Meta : l'API WhatsApp Cloud sans compte Meta.

Pour les tests (dans le même processus, par `httpx.ASGITransport`) et pour
essayer le service en local. Il :

- reçoit les envois (`POST /{version}/{numéro}/messages`), vérifie le jeton
  et les **limites de WhatsApp** comme Meta (3 boutons de 20 caractères,
  10 lignes de liste...), et répond un wamid ou une erreur au format Meta ;
- simule les pannes de Meta : erreur, réponse 500, coupure (`fail_next`) ;
- applique la **fenêtre de 24 h** comme Meta : un message libre à quelqu'un
  qui n'a pas écrit depuis 24 h est accepté, puis refusé par un statut
  `failed` (erreur 131047) ; seuls les modèles approuvés (`templates`)
  passent hors fenêtre ;
- garde les statuts que Meta enverrait pour les notifications (porteuses de
  `biz_opaque_callback_data`) et les rend en webhook signé
  (`status_webhook`), ainsi que les événements de modèle (`template_event`) ;
- fabrique des webhooks **signés** comme Meta (`webhook_*`), avec BSUID et
  numéro facultatif, et peut les poster au service (`POST /_fake/ecrire`).

Essai en local (trois terminaux, backend déjà lancé) :

    # 1. Faux Meta, sur le port 8011
    python -m whatsapp_bot.fake_meta
    # 2. Service WhatsApp, qui envoie au faux Meta
    WHATSAPP_GRAPH_URL=http://127.0.0.1:8011/v23.0 python -m whatsapp_bot
    # 3. Écrire comme un client, puis lire les réponses
    curl -X POST http://127.0.0.1:8011/_fake/ecrire -H 'Content-Type: application/json' -d '{"text": "Bonjour"}'
    curl -X POST http://127.0.0.1:8011/_fake/ecrire -H 'Content-Type: application/json' -d '{"choice": "lang:fr"}'
    curl http://127.0.0.1:8011/_fake/envoyes

Les deux processus lisent les mêmes `WHATSAPP_APP_SECRET`,
`WHATSAPP_ACCESS_TOKEN` et `WHATSAPP_PHONE_NUMBER_ID` du `.env`.
`WHATSAPP_WEBHOOK_TARGET` (défaut http://127.0.0.1:8003/webhook) : où le
faux Meta poste les messages écrits.
"""

from __future__ import annotations

import itertools
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from typing import Callable

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from whatsapp_bot import meta, signature

DEFAULT_BSUID = "CD.1000000000000000001"
DEFAULT_PHONE = "243810000001"
WINDOW_SECONDS = 24 * 3600
# Modèles approuvés d'office (backend/app/modeles_whatsapp.py).
DEFAULT_TEMPLATES = {("nexis_suivi", "fr"): "APPROVED", ("nexis_suivi", "en"): "APPROVED"}


def _meta_error(status: int, code: int, message: str) -> JSONResponse:
    return JSONResponse(
        {"error": {"message": message, "type": "OAuthException", "code": code, "fbtrace_id": secrets.token_hex(8)}},
        status_code=status,
    )


@dataclass
class Sent:
    """Un envoi accepté, lu par les tests."""

    wamid: str
    to: str | None
    recipient: str | None
    body: dict

    @property
    def kind(self) -> str:
        if self.body.get("type") == "interactive":
            return self.body["interactive"]["type"]  # button | list | location_request_message
        return self.body.get("type", "")

    @property
    def text(self) -> str:
        if self.body.get("type") == "text":
            return self.body["text"]["body"]
        if self.body.get("type") == "interactive":
            return self.body["interactive"]["body"]["text"]
        return ""

    @property
    def callback(self) -> str | None:
        return self.body.get("biz_opaque_callback_data")

    @property
    def template(self) -> dict | None:
        return self.body.get("template") if self.body.get("type") == "template" else None

    @property
    def choices(self) -> list[tuple[str, str]]:
        """(identifiant, libellé) des boutons ou des lignes de liste."""
        if self.kind == "button":
            return [(b["reply"]["id"], b["reply"]["title"]) for b in self.body["interactive"]["action"]["buttons"]]
        if self.kind == "list":
            return [(row["id"], row["title"]) for s in self.body["interactive"]["action"]["sections"] for row in s["rows"]]
        return []


@dataclass
class FakeMeta:
    access_token: str
    phone_number_id: str
    app_secret: str
    sent: list[Sent] = field(default_factory=list)
    read: list[str] = field(default_factory=list)
    # Pannes à venir, dans l'ordre : "error" (refus 400 de Meta), "server"
    # (500), "timeout" (coupure après réception : réponse perdue).
    failures: list[str] = field(default_factory=list)
    # Horloge de Meta (secondes), avançable dans les tests.
    clock: Callable[[], float] = time.time
    # Dernier message reçu de chaque personne (numéro et BSUID) : fenêtre de 24 h.
    inbound: dict[str, float] = field(default_factory=dict)
    # Modèles connus : (nom, langue) → APPROVED, PAUSED, DISABLED...
    templates: dict[tuple[str, str], str] = field(default_factory=lambda: dict(DEFAULT_TEMPLATES))
    # Statuts que Meta enverrait (notifications seulement), pas encore livrés.
    statuses: list[dict] = field(default_factory=list)
    _counter: itertools.count = field(default_factory=lambda: itertools.count(1))

    def fail_next(self, *kinds: str) -> None:
        self.failures.extend(kinds)

    def wamid(self) -> str:
        return f"wamid.FAKE{next(self._counter):08d}"

    # --- Webhooks signés --------------------------------------------------------

    def webhook(self, message: dict, *, bsuid: str = DEFAULT_BSUID, phone: str | None = DEFAULT_PHONE, name: str = "Client") -> dict:
        contact = {"profile": {"name": name}, "user_id": bsuid}
        now = self.clock()
        message = {"from_user_id": bsuid, "timestamp": str(int(now)), **message}
        self.inbound[bsuid] = now
        if phone is not None:
            contact["wa_id"] = phone
            message["from"] = phone
            self.inbound[phone] = now
        message.setdefault("id", self.wamid())
        return {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "WABA_FAKE",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"display_phone_number": "243800000000", "phone_number_id": self.phone_number_id},
                                "contacts": [contact],
                                "messages": [message],
                            },
                        }
                    ],
                }
            ],
        }

    def text_message(self, body: str, **who) -> dict:
        return self.webhook({"type": "text", "text": {"body": body}}, **who)

    def choice_message(self, choice_id: str, *, list_row: bool = False, **who) -> dict:
        kind = "list_reply" if list_row else "button_reply"
        reply = {"type": kind, kind: {"id": choice_id, "title": choice_id}}
        return self.webhook({"type": "interactive", "interactive": reply}, **who)

    def template_reply(self, payload: str, text: str = "Voir les détails", **who) -> dict:
        """Appui sur le bouton d'un modèle (`type: button`)."""
        return self.webhook({"type": "button", "button": {"payload": payload, "text": text}}, **who)

    def media_message(self, kind: str = "image", **who) -> dict:
        return self.webhook({"type": kind, kind: {"id": "MEDIA_FAKE", "mime_type": "image/jpeg"}}, **who)

    def location_message(self, latitude: float, longitude: float, **who) -> dict:
        return self.webhook({"type": "location", "location": {"latitude": latitude, "longitude": longitude}}, **who)

    def _envelope(self, change: dict) -> dict:
        entry = {"id": "WABA_FAKE", "time": int(self.clock()), "changes": [change]}
        return {"object": "whatsapp_business_account", "entry": [entry]}

    def status(self, sent: "Sent", status: str, *, error_code: int | None = None) -> dict:
        """Un statut de Meta pour un envoi accepté."""
        raw = {
            "id": sent.wamid,
            "status": status,
            "timestamp": str(int(self.clock())),
            "recipient_id": sent.to or sent.recipient,
        }
        if sent.callback:
            raw["biz_opaque_callback_data"] = sent.callback
        if error_code is not None:
            raw["errors"] = [{"code": error_code, "title": "error", "message": "error"}]
        return raw

    def status_webhook(self, statuses: list[dict] | None = None) -> dict:
        """Webhook des statuts donnés, ou de ceux que Meta a en attente
        (qui sont alors vidés)."""
        if statuses is None:
            statuses, self.statuses = self.statuses, []
        return self._envelope(
            {
                "field": "messages",
                "value": {
                    "messaging_product": "whatsapp",
                    "metadata": {"display_phone_number": "243800000000", "phone_number_id": self.phone_number_id},
                    "statuses": statuses,
                },
            }
        )

    def template_event(self, name: str, language: str, event: str, reason: str = "NONE") -> dict:
        """Webhook de Meta : modèle approuvé, refusé, en pause..."""
        return self._envelope(
            {
                "field": "message_template_status_update",
                "value": {
                    "event": event,
                    "message_template_id": 1234567890,
                    "message_template_name": name,
                    "message_template_language": language,
                    "reason": reason,
                },
            }
        )

    def in_window(self, address: str | None) -> bool:
        seen = self.inbound.get(address or "")
        return seen is not None and self.clock() - seen < WINDOW_SECONDS

    def signed(self, payload: dict) -> tuple[bytes, dict]:
        body = json.dumps(payload).encode()
        return body, {signature.HEADER: signature.sign(self.app_secret, body), "Content-Type": "application/json"}

    # --- API d'envoi --------------------------------------------------------------

    def app(self) -> FastAPI:
        fake = self
        api = FastAPI(title="Faux Meta", docs_url=None, redoc_url=None, openapi_url=None)

        @api.post("/{version}/{phone_number_id}/messages")
        async def messages(version: str, phone_number_id: str, request: Request):
            if request.headers.get("Authorization") != f"Bearer {fake.access_token}":
                return _meta_error(401, 190, "Invalid OAuth access token")
            if phone_number_id != fake.phone_number_id:
                return _meta_error(400, 100, "Unsupported post request")
            body = await request.json()
            if body.get("status") == "read":
                fake.read.append(str(body.get("message_id")))
                return {"success": True}
            if fake.failures:
                failure = fake.failures.pop(0)
                if failure == "error":
                    return _meta_error(400, 131026, "Message undeliverable")
                if failure == "server":
                    return _meta_error(500, 2, "Service temporarily unavailable")
                if failure == "timeout":
                    raise httpx.ReadTimeout("réponse perdue")
            problem = _invalid(body)
            if problem:
                return _meta_error(400, 131009, f"Parameter value is not valid: {problem}")
            if body.get("type") == "template":
                refusal = fake._template_refusal(body["template"])
                if refusal:
                    return refusal
            wamid = fake.wamid()
            sent_message = Sent(wamid=wamid, to=body.get("to"), recipient=body.get("recipient"), body=body)
            fake.sent.append(sent_message)
            address = body.get("to") or body.get("recipient")
            if body.get("type") != "template" and not fake.in_window(address):
                # Comme Meta : accepté, puis refusé par un statut.
                fake.statuses.append(fake.status(sent_message, "failed", error_code=131047))
            elif sent_message.callback:
                fake.statuses.append(fake.status(sent_message, "delivered"))
            contact = {"input": body.get("to") or body.get("recipient")}
            return {"messaging_product": "whatsapp", "contacts": [contact], "messages": [{"id": wamid}]}

        @api.get("/_fake/envoyes")
        async def sent():
            return [{"wamid": s.wamid, "type": s.kind, "text": s.text, "choix": s.choices} for s in fake.sent]

        @api.post("/_fake/ecrire")
        async def write(request: Request):
            """Écrit comme un client : `text`, `choice` (bouton ou ligne),
            `media` ou `latitude`/`longitude` ; `bsuid`, `phone` facultatifs."""
            order = await request.json()
            who = {"bsuid": order.get("bsuid", DEFAULT_BSUID), "phone": order.get("phone", DEFAULT_PHONE)}
            if "text" in order:
                payload = fake.text_message(str(order["text"]), **who)
            elif "choice" in order:
                payload = fake.choice_message(str(order["choice"]), list_row=str(order["choice"]).startswith("menu:"), **who)
            elif "latitude" in order:
                payload = fake.location_message(float(order["latitude"]), float(order["longitude"]), **who)
            else:
                payload = fake.media_message(str(order.get("media", "image")), **who)
            body, headers = fake.signed(payload)
            target = os.getenv("WHATSAPP_WEBHOOK_TARGET", "http://127.0.0.1:8003/webhook")
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(target, content=body, headers=headers)
            return {"webhook": response.status_code}

        return api

    def _template_refusal(self, template: dict) -> JSONResponse | None:
        language = (template.get("language") or {}).get("code")
        state = self.templates.get((template.get("name"), language))
        if state is None:
            return _meta_error(404, 132001, "Template name does not exist in the translation")
        if state == "PAUSED":
            return _meta_error(400, 132015, "Template is paused")
        if state != "APPROVED":
            return _meta_error(400, 132016, "Template is disabled")
        body = [c for c in template.get("components") or [] if c.get("type") == "body"]
        values = [p.get("text") or "" for c in body for p in c.get("parameters") or []]
        if len(values) != 1 or any(not v or "\n" in v or "\t" in v or "     " in v for v in values):
            return _meta_error(400, 132000, "Number of parameters does not match the expected number of params")
        buttons = [c for c in template.get("components") or [] if c.get("type") == "button"]
        if len(buttons) != 1 or not (buttons[0].get("parameters") or [{}])[0].get("payload"):
            return _meta_error(400, 132000, "Button parameter missing")
        return None


def _invalid(body: dict) -> str | None:
    """Les limites que Meta applique, vérifiées comme lui."""
    if body.get("messaging_product") != "whatsapp":
        return "messaging_product"
    if not (body.get("to") or body.get("recipient")):
        return "to"
    kind = body.get("type")
    if kind == "text":
        text = (body.get("text") or {}).get("body") or ""
        return None if 0 < len(text) <= meta.MAX_TEXT_BODY else "text.body"
    if kind == "template":
        return None if (body.get("template") or {}).get("name") else "template.name"
    if kind != "interactive":
        return "type"
    interactive = body.get("interactive") or {}
    text = (interactive.get("body") or {}).get("text") or ""
    if not 0 < len(text) <= meta.MAX_INTERACTIVE_BODY:
        return "interactive.body.text"
    action = interactive.get("action") or {}
    if interactive.get("type") == "button":
        buttons = action.get("buttons") or []
        if not 0 < len(buttons) <= meta.MAX_BUTTONS:
            return "buttons"
        titles = [(b.get("reply") or {}).get("title") or "" for b in buttons]
        ids = [(b.get("reply") or {}).get("id") or "" for b in buttons]
        if any(not 0 < len(t) <= meta.MAX_BUTTON_TITLE for t in titles) or len(set(ids)) != len(ids):
            return "button.title"
        return None
    if interactive.get("type") == "list":
        if not 0 < len(action.get("button") or "") <= meta.MAX_BUTTON_TITLE:
            return "action.button"
        rows = [row for section in action.get("sections") or [] for row in section.get("rows") or []]
        if not 0 < len(rows) <= meta.MAX_LIST_ROWS:
            return "rows"
        for row in rows:
            if not 0 < len(row.get("title") or "") <= meta.MAX_ROW_TITLE:
                return "row.title"
            if len(row.get("description") or "") > meta.MAX_ROW_DESCRIPTION:
                return "row.description"
        return None
    if interactive.get("type") == "location_request_message":
        return None if action.get("name") == "send_location" else "action.name"
    return "interactive.type"


def main() -> None:
    import uvicorn
    from dotenv import load_dotenv

    load_dotenv()
    fake = FakeMeta(
        access_token=os.getenv("WHATSAPP_ACCESS_TOKEN", ""),
        phone_number_id=os.getenv("WHATSAPP_PHONE_NUMBER_ID", ""),
        app_secret=os.getenv("WHATSAPP_APP_SECRET", ""),
    )
    if not (fake.access_token and fake.phone_number_id and fake.app_secret):
        raise SystemExit("WHATSAPP_ACCESS_TOKEN, WHATSAPP_PHONE_NUMBER_ID et WHATSAPP_APP_SECRET sont nécessaires (.env)")
    uvicorn.run(fake.app(), host="127.0.0.1", port=int(os.getenv("FAKE_META_PORT", "8011")))


if __name__ == "__main__":
    main()
