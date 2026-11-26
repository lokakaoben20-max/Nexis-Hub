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


def _is_refusal(answer) -> bool:
    """Un refus métier peut porter un code 5xx (ex. 503 `terms_unavailable`) :
    c'est une réponse claire, pas une panne."""
    detail = answer.get("detail") if isinstance(answer, dict) else None
    return isinstance(detail, dict) and isinstance(detail.get("code"), str)
