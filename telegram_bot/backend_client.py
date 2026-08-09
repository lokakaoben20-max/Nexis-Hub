"""Client backend V5 partagé par les flows extraits de `main.py` (Phase 3).

Déplacé depuis `main.py` — regroupe les helpers `sync_*`/`fetch_*` utilisés par
`telegram_bot/registration.py`, `telegram_bot/mission.py` et `telegram_bot/payment.py`.
`main.py` importe les fonctions ci-dessous au lieu de les redéfinir, pour que les
handlers hors scope qui les utilisent encore n'aient rien à changer.

Double écriture maintenue (backend + `db.py`) pour toutes les écritures de ce module :
`find_matching_providers` (flow mission, pas migré) et la Mini App lisent encore
`db.py` pour le statut/les services/la langue du prestataire — couper l'écriture locale
maintenant leur ferait lire une donnée périmée. Voir V5_MIGRATION_PLAN.md, Phase 3.
"""

import json
import os

import httpx
from dotenv import load_dotenv

from db import create_user, get_mission_by_id, get_provider_by_telegram_id, get_user_by_telegram_id

load_dotenv()
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
BACKEND_AUTH_HEADERS = {"X-API-Key": BACKEND_API_KEY}


async def _safe_backend_call(coro):
    try:
        return await coro
    except Exception:
        return None


async def sync_user_to_backend(telegram_id: int, first_name: str | None = None, phone_number: str | None = None, language: str = "fr") -> dict:
    payload = {
        "telegram_id": telegram_id,
        "first_name": first_name or "Client",
        "phone_number": phone_number,
        "language": language,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/users", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_provider_to_backend(
    telegram_id: int,
    full_name: str,
    phone_number: str | None = None,
    services: list[str] | None = None,
    communes: list[str] | None = None,
    language: str = "fr",
    id_document_file_id: str | None = None,
    selfie_file_id: str | None = None,
    portfolio_file_ids: list[str] | None = None,
) -> dict:
    payload = {
        "telegram_id": telegram_id,
        "full_name": full_name,
        "phone_number": phone_number,
        "services": services or [],
        "communes": communes or [],
        "language": language,
        "id_document_file_id": id_document_file_id,
        "selfie_file_id": selfie_file_id,
        "portfolio_file_ids": portfolio_file_ids,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_provider_services_to_backend(telegram_id: int, services: list[str]) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/services", json={"services": services})
        response.raise_for_status()
        return response.json()


async def sync_provider_status_to_backend(telegram_id: int, status: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/status", json={"status": status})
        response.raise_for_status()
        return response.json()


async def sync_provider_verified_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/verify")
        response.raise_for_status()
        return response.json()


async def sync_provider_suspended_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/suspend")
        response.raise_for_status()
        return response.json()


async def sync_provider_unsuspended_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/unsuspend")
        response.raise_for_status()
        return response.json()


async def sync_user_language_to_backend(telegram_id: int, language: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/users/{telegram_id}/language", json={"language": language})
        response.raise_for_status()
        return response.json()


async def sync_user_name_to_backend(telegram_id: int, first_name: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/users/{telegram_id}/name", json={"first_name": first_name})
        response.raise_for_status()
        return response.json()


async def sync_provider_language_to_backend(telegram_id: int, language: str) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.patch(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/language", json={"language": language})
        response.raise_for_status()
        return response.json()


async def sync_provider_ignored_reset_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/ignored/reset")
        response.raise_for_status()
        return response.json()


async def sync_provider_ignored_increment_to_backend(telegram_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/providers/{telegram_id}/ignored")
        response.raise_for_status()
        return response.json()


async def sync_mission_to_backend(telegram_id: int, mission_id: int, data: dict) -> dict:
    payload = {
        "telegram_id": telegram_id,
        "mission_id": mission_id,
        "service": data.get("service", "service_autre"),
        "commune": data.get("commune", "Autre commune"),
        "currency": data.get("currency", "USD"),
        "description": data.get("description", ""),
        "urgent": bool(data.get("urgent", False)),
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/missions", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_quote_to_backend(mission_id: int, provider_telegram_id: int, amount: float, currency: str, delay_hours: int, message: str = "") -> dict:
    payload = {
        "mission_id": mission_id,
        "provider_telegram_id": provider_telegram_id,
        "amount": amount,
        "currency": currency,
        "delay_hours": delay_hours,
        "message": message,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_quote_accept_to_backend(backend_quote_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes/{backend_quote_id}/accept")
        response.raise_for_status()
        return response.json()


async def sync_quote_reject_to_backend(backend_quote_id: int) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/quotes/{backend_quote_id}/reject")
        response.raise_for_status()
        return response.json()


async def sync_mission_status_to_backend(
    mission_id: int,
    status: str,
    payment_status: str | None = None,
    dispute_reason: str | None = None,
    refund_amount: float | None = None,
    net_provider: float | None = None,
) -> dict:
    """`refund_amount`/`net_provider` : résolution de litige. Combinables avec
    `payment_status="released"` pour un partage à l'amiable (le prestataire
    reçoit `net_provider` — sa part réduite, PAS le net_provider posé au
    paiement escrow initial — le client `refund_amount`, dans le même appel).
    Sans `net_provider` explicite, le backend garderait la valeur pleine déjà
    stockée et sur-créditerait le prestataire — voir backend/app/main.py::
    update_mission_status.
    """
    payload = {"mission_id": mission_id, "status": status}
    if payment_status:
        payload["payment_status"] = payment_status
    if dispute_reason is not None:
        payload["dispute_reason"] = dispute_reason
    if refund_amount is not None:
        payload["refund_amount"] = refund_amount
    if net_provider is not None:
        payload["net_provider"] = net_provider
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/missions/status", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_payment_to_backend(
    quote_id: int,
    payment_status: str,
    mission_id: int | None = None,
    amounts: dict | None = None,
    via_wallet: bool = False,
) -> dict:
    """`amounts` : le dict retourné par `db.mark_quote_paid`/`mark_quote_paid_with_wallet`
    (mêmes clés : commission_amount, tola_fee, aggregator_fee, total_client,
    net_provider, mobile_money_ref, operator, quote). Quand fourni, le backend
    reflète la transaction et débite le wallet (si `via_wallet`) sans revalider
    — db.py reste la source de vérité, voir backend/app/main.py::PaymentPayload.
    """
    payload = {"quote_id": quote_id, "payment_status": payment_status}
    if mission_id is not None:
        payload["mission_id"] = mission_id
    if amounts is not None:
        quote = amounts["quote"]
        payload.update(
            {
                "amount": quote["amount"],
                "currency": quote["currency"],
                "commission_amount": amounts["commission_amount"],
                "tola_fee": amounts["tola_fee"],
                "aggregator_fee": amounts["aggregator_fee"],
                "total_client": amounts["total_client"],
                "net_provider": amounts["net_provider"],
                "mobile_money_ref": amounts["mobile_money_ref"],
                "operator": amounts["operator"],
                "via_wallet": via_wallet,
            }
        )
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/payments", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_review_to_backend(mission_id: int, client_telegram_id: int, rating: int, comment: str = "") -> dict:
    payload = {
        "mission_id": mission_id,
        "client_telegram_id": client_telegram_id,
        "rating": rating,
        "comment": comment,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/reviews", json=payload)
        response.raise_for_status()
        return response.json()


async def persist_mission_creation(telegram_id: int, mission_id: int, data: dict) -> dict:
    local_mission = get_mission_by_id(mission_id)
    if local_mission is None:
        local_mission = {"id": mission_id, "status": "created"}
    backend_result = await _safe_backend_call(sync_mission_to_backend(telegram_id, mission_id, data))
    return {
        "local": local_mission,
        "backend": backend_result,
    }


async def fetch_backend_profile(telegram_id: int) -> dict | None:
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/profile/{telegram_id}")
            response.raise_for_status()
            return response.json()
    except Exception:
        return None


async def load_profile_from_backend(telegram_id: int, fallback_user: dict | None = None) -> dict:
    backend_profile = await fetch_backend_profile(telegram_id)
    if backend_profile:
        return backend_profile
    return {"client": fallback_user or {"telegram_id": telegram_id, "first_name": "Client"}, "provider": None, "client_missions": [], "provider_missions": []}


async def get_state_language(state) -> str:
    data = await state.get_data()
    return data.get("language", "fr")


async def get_user_language(telegram_id: int) -> str:
    backend_profile = await fetch_backend_profile(telegram_id)
    client_data = backend_profile.get("client") if backend_profile else None
    if client_data and client_data.get("language"):
        return client_data["language"]
    user = get_user_by_telegram_id(telegram_id)
    return user["language"] if user else "fr"


async def get_provider_language(telegram_id: int) -> str:
    backend_profile = await fetch_backend_profile(telegram_id)
    provider_data = backend_profile.get("provider") if backend_profile else None
    if provider_data and provider_data.get("language"):
        return provider_data["language"]
    provider = get_provider_by_telegram_id(telegram_id)
    if not provider:
        return "fr"
    try:
        languages = json.loads(provider["languages_spoken"] or '["fr"]')
    except json.JSONDecodeError:
        return "fr"
    return languages[0] if languages else "fr"


async def persist_client_registration(telegram_id: int, first_name: str | None = None, phone_number: str | None = None, language: str = "fr") -> dict:
    local_user = create_user(
        telegram_id=telegram_id,
        phone_number=phone_number,
        first_name=first_name or "",
        language=language,
    )
    backend_result = await _safe_backend_call(
        sync_user_to_backend(
            telegram_id=telegram_id,
            first_name=first_name,
            phone_number=phone_number,
            language=language,
        )
    )
    return {"local": local_user, "backend": backend_result}
