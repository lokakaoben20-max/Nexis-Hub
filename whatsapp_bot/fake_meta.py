"""Faux serveur Meta : l'API WhatsApp Cloud sans compte Meta.

Pour les tests (dans le même processus, par `httpx.ASGITransport`) et pour
essayer le service en local. Il :

- reçoit les envois (`POST /{version}/{numéro}/messages`), vérifie le jeton
  et les **limites de WhatsApp** comme Meta (3 boutons de 20 caractères,
  10 lignes de liste...), et répond un wamid ou une erreur au format Meta ;
- simule les pannes de Meta : erreur, réponse 500, coupure (`fail_next`) ;
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
from dataclasses import dataclass, field

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from whatsapp_bot import meta, signature

DEFAULT_BSUID = "CD.1000000000000000001"
DEFAULT_PHONE = "243810000001"


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
    _counter: itertools.count = field(default_factory=lambda: itertools.count(1))

    def fail_next(self, *kinds: str) -> None:
        self.failures.extend(kinds)

    def wamid(self) -> str:
        return f"wamid.FAKE{next(self._counter):08d}"

    # --- Webhooks signés --------------------------------------------------------

    def webhook(self, message: dict, *, bsuid: str = DEFAULT_BSUID, phone: str | None = DEFAULT_PHONE, name: str = "Client") -> dict:
        contact = {"profile": {"name": name}, "user_id": bsuid}
        message = {"from_user_id": bsuid, "timestamp": "1764150000", **message}
        if phone is not None:
            contact["wa_id"] = phone
            message["from"] = phone
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

    def media_message(self, kind: str = "image", **who) -> dict:
        return self.webhook({"type": kind, kind: {"id": "MEDIA_FAKE", "mime_type": "image/jpeg"}}, **who)

    def location_message(self, latitude: float, longitude: float, **who) -> dict:
        return self.webhook({"type": "location", "location": {"latitude": latitude, "longitude": longitude}}, **who)

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
            wamid = fake.wamid()
            fake.sent.append(Sent(wamid=wamid, to=body.get("to"), recipient=body.get("recipient"), body=body))
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
