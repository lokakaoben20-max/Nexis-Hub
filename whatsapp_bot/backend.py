"""Appels au backend, au nom de la personne qui écrit.

Clé de service du canal WhatsApp (`BACKEND_API_KEY_WHATSAPP`) et identité de
l'expéditeur (`X-Actor-Channel: whatsapp`, `X-Actor-Id: <BSUID>`), lue dans
un webhook signé par Meta. Toute écriture porte la clé d'idempotence du
message WhatsApp qui l'a demandée (`Idempotency-Key: <wamid>`) : un message
rejoué rend la même réponse, sans rien refaire (backend/app/idempotency.py).

Backend injoignable, ou réponse inattendue : `BackendUnavailable`, rien n'a
été fait. Refus métier : `Refused` avec le code stable du backend. Rien
n'est gardé pour être rejoué plus tard.
"""

from __future__ import annotations

import httpx

TIMEOUT_SECONDS = 10.0


class BackendUnavailable(Exception):
    """Pas de réponse claire du backend : rien n'a été fait."""


class Refused(Exception):
    def __init__(self, code: str, status: int, detail: dict | None = None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.detail = detail or {}


class Backend:
    def __init__(self, base_url: str, api_key: str, *, transport=None):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._transport = transport

    def _headers(self, bsuid: str | None, idempotency_key: str | None) -> dict:
        headers = {"X-API-Key": self._api_key}
        if bsuid is not None:
            headers.update({"X-Actor-Channel": "whatsapp", "X-Actor-Id": bsuid})
        if idempotency_key is not None:
            headers["Idempotency-Key"] = idempotency_key
        return headers

    async def _call(self, method: str, path: str, bsuid: str | None, *, body: dict | None = None, key: str | None = None) -> dict:
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=self._transport) as client:
                response = await client.request(
                    method, f"{self._base_url}{path}", json=body, headers=self._headers(bsuid, key)
                )
        except httpx.HTTPError as error:
            raise BackendUnavailable(type(error).__name__) from error
        try:
            answer = response.json()
        except ValueError as error:
            raise BackendUnavailable(f"http_{response.status_code}") from error
        if response.status_code >= 500 and not _is_refusal(answer):
            raise BackendUnavailable(f"http_{response.status_code}")
        if response.status_code >= 400:
            detail = answer.get("detail") if isinstance(answer, dict) else None
            if not isinstance(detail, dict) or not isinstance(detail.get("code"), str):
                raise BackendUnavailable(f"http_{response.status_code}")
            raise Refused(detail["code"], response.status_code, detail)
        if not isinstance(answer, dict) or answer.get("status") != "ok":
            raise BackendUnavailable("unexpected_answer")
        return answer

    async def profile(self, bsuid: str) -> dict:
        return await self._call("GET", "/api/me/profile", bsuid)

    async def terms(self, bsuid: str) -> dict:
        return await self._call("GET", "/api/me/terms", bsuid)

    async def register(
        self, bsuid: str, key: str, *, name: str, language: str, phone: str | None, documents: list[dict]
    ) -> dict:
        body = {
            "display_name": name,
            "language": language,
            "terms": {"surface": "whatsapp", "documents": documents},
        }
        if phone:
            body["phone"] = phone
        return await self._call("POST", "/api/whatsapp/client", bsuid, body=body, key=key)

    async def accept_terms(self, bsuid: str, key: str, *, role: str, documents: list[dict]) -> dict:
        body = {"role": role, "surface": "whatsapp", "documents": documents}
        return await self._call("POST", "/api/me/terms", bsuid, body=body, key=key)

    async def terms_text(self, document_key: str, version: str) -> dict:
        """Texte exact d'une version des conditions (aucune identité : le
        texte est le même pour tous)."""
        return await self._call("GET", f"/api/legal/documents/{document_key}/{version}", None)

    async def set_language(self, bsuid: str, key: str, language: str) -> dict:
        return await self._call("PATCH", "/api/me/language", bsuid, body={"language": language}, key=key)

    async def services(self, bsuid: str) -> dict:
        """Catalogue actif et communes servies, dans l'ordre d'affichage."""
        return await self._call("GET", "/api/services", bsuid)

    async def create_mission(self, bsuid: str, key: str, request: dict) -> dict:
        """Mission du client qui écrit. `request["creation_key"]` est la même
        à chaque essai de la même demande : un double appui ou un message
        renvoyé ne crée qu'une mission."""
        return await self._call("POST", "/api/bot/missions", bsuid, body=request, key=key)

    async def my_missions(self, bsuid: str, limit: int = 9) -> dict:
        """Dernières missions commandées par la personne."""
        return await self._call("GET", f"/api/me/missions?role=client&limit={limit}", bsuid)

    async def mission_quotes(self, bsuid: str, mission_id: int) -> dict:
        """La mission et ses devis (client de la mission seulement)."""
        return await self._call("GET", f"/api/bot/missions/{mission_id}/quotes", bsuid)

    async def quote(self, bsuid: str, quote_id: int) -> dict:
        return await self._call("GET", f"/api/bot/quotes/{quote_id}", bsuid)

    async def accept_quote(self, bsuid: str, key: str, quote_id: int) -> dict:
        return await self._call("POST", f"/api/bot/quotes/{quote_id}/accept", bsuid, key=key)

    async def reject_quote(self, bsuid: str, key: str, quote_id: int) -> dict:
        return await self._call("POST", f"/api/bot/quotes/{quote_id}/reject", bsuid, key=key)

    async def wallet(self, bsuid: str) -> dict:
        return await self._call("GET", "/api/me/wallet", bsuid)

    async def fund_wallet(self, bsuid: str, key: str, mission_id: int, *, quote_id: int) -> dict:
        """Paie la mission par le wallet, sur son devis accepté : montant et
        prestataire sont relus par le backend."""
        body = {"method": "wallet", "quote_id": quote_id}
        return await self._call("POST", f"/api/bot/missions/{mission_id}/fund", bsuid, body=body, key=key)

    async def create_payment_intent(self, bsuid: str, key: str, mission_id: int, *, quote_id: int, phone: str, operator: str) -> dict:
        """Demande de paiement Mobile Money envoyée au téléphone ; seule la
        confirmation de l'agrégateur paie la mission."""
        body = {"quote_id": quote_id, "phone": phone, "operator": operator}
        return await self._call("POST", f"/api/bot/missions/{mission_id}/payment-intents", bsuid, body=body, key=key)

    async def payment_intent(self, bsuid: str, intent_id: int) -> dict:
        return await self._call("GET", f"/api/bot/payment-intents/{intent_id}", bsuid)

    # --- Suivi d'une demande payée (étape 7) ---------------------------------------

    async def presence(self, bsuid: str, mission_id: int) -> dict:
        """État de l'arrivée ; le code de présence n'est donné qu'au client."""
        return await self._call("GET", f"/api/bot/missions/{mission_id}/presence", bsuid)

    async def presence_confirm(self, bsuid: str, key: str, mission_id: int) -> dict:
        return await self._call("POST", f"/api/bot/missions/{mission_id}/presence/confirm", bsuid, key=key)

    async def presence_not_yet(self, bsuid: str, key: str, mission_id: int) -> dict:
        return await self._call("POST", f"/api/bot/missions/{mission_id}/presence/not-yet", bsuid, key=key)

    async def presence_wrong_person(self, bsuid: str, key: str, mission_id: int) -> dict:
        """Gèle l'argent : un litige est ouvert."""
        return await self._call("POST", f"/api/bot/missions/{mission_id}/presence/wrong-person", bsuid, key=key)

    async def confirm_completion(self, bsuid: str, key: str, mission_id: int) -> dict:
        """Paie le prestataire, une seule fois."""
        return await self._call("POST", f"/api/bot/missions/{mission_id}/confirm", bsuid, key=key)

    async def open_dispute(self, bsuid: str, key: str, mission_id: int, *, reason: str) -> dict:
        return await self._call("POST", f"/api/bot/missions/{mission_id}/dispute", bsuid, body={"reason": reason}, key=key)

    async def review(self, bsuid: str, key: str, mission_id: int, *, rating: int, comment: str | None) -> dict:
        body = {"mission_id": mission_id, "rating": rating, "comment": comment}
        return await self._call("POST", "/api/bot/reviews", bsuid, body=body, key=key)

    # --- Litige (étape 7b) ------------------------------------------------------------

    async def contest_dispute(self, bsuid: str, key: str, mission_id: int, *, reason: str) -> dict:
        """Conteste la première décision de NexisHub, une fois, avant son exécution."""
        return await self._call("POST", f"/api/bot/missions/{mission_id}/dispute/contest", bsuid, body={"reason": reason}, key=key)

    async def propose_settlement(self, bsuid: str, key: str, mission_id: int, *, kind: str, percentage: int | None) -> dict:
        """Proposition d'accord au prestataire ; les montants sont calculés
        et figés par le backend."""
        body = {"kind": kind, "provider_percentage": percentage}
        return await self._call("POST", f"/api/bot/missions/{mission_id}/dispute/offers", bsuid, body=body, key=key)

    async def wallet_history(self, bsuid: str, limit: int = 5) -> dict:
        return await self._call("GET", f"/api/me/wallet/history?limit={limit}", bsuid)


def _is_refusal(answer) -> bool:
    """Un refus métier peut porter un code 5xx (ex. 503 `terms_unavailable`) :
    c'est une réponse claire, pas une panne."""
    detail = answer.get("detail") if isinstance(answer, dict) else None
    return isinstance(detail, dict) and isinstance(detail.get("code"), str)
