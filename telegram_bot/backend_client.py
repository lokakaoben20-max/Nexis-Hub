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

import asyncio
import json
import logging
import os

import httpx
from dotenv import load_dotenv

from db import (
    count_backend_outbox,
    create_user,
    delete_backend_outbox_entry,
    enqueue_backend_call,
    get_backend_outbox,
    get_mission_by_id,
    get_provider_by_telegram_id,
    get_user_by_telegram_id,
    mark_backend_outbox_failure,
)

load_dotenv()
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
BACKEND_AUTH_HEADERS = {"X-API-Key": BACKEND_API_KEY}
logger = logging.getLogger(__name__)


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


async def sync_service_request_to_backend(provider_telegram_id: int, service_name: str, description: str = "") -> dict:
    payload = {
        "provider_telegram_id": provider_telegram_id,
        "service_name": service_name,
        "description": description,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/service-requests", json=payload)
        response.raise_for_status()
        return response.json()


async def sync_service_request_status_to_backend(backend_request_id: int, status: str, admin_note: str = "") -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.patch(
            f"{BACKEND_BASE_URL}/api/bot/service-requests/{backend_request_id}/status",
            json={"status": status, "admin_note": admin_note},
        )
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
    payload = _mission_status_payload(mission_id, status, payment_status, dispute_reason, refund_amount, net_provider)
    return await _post_backend(MISSION_STATUS_PATH, payload)


def _mission_status_payload(mission_id, status, payment_status=None, dispute_reason=None, refund_amount=None, net_provider=None) -> dict:
    payload = {"mission_id": mission_id, "status": status}
    if payment_status:
        payload["payment_status"] = payment_status
    if dispute_reason is not None:
        payload["dispute_reason"] = dispute_reason
    if refund_amount is not None:
        payload["refund_amount"] = refund_amount
    if net_provider is not None:
        payload["net_provider"] = net_provider
    return payload


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
    payload = _payment_payload(quote_id, payment_status, mission_id, amounts, via_wallet)
    return await _post_backend(PAYMENT_PATH, payload)


def _payment_payload(quote_id, payment_status, mission_id=None, amounts=None, via_wallet=False) -> dict:
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
    return payload


async def _post_backend(path: str, payload: dict) -> dict:
    async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
        response = await client.post(f"{BACKEND_BASE_URL}{path}", json=payload)
        response.raise_for_status()
        return response.json()


# --- File d'attente des appels qui déplacent de l'argent -------------------
# Paiement escrow, libération, remboursement et statuts de mission passaient
# par `_safe_backend_call` : backend coupé = appel perdu, wallet backend faux
# pour toujours. Ils passent maintenant par `backend_outbox` (db.py) : mis en
# file, puis envoyés dans l'ordre d'arrivée. Un appel qui échoue reste en
# file et bloque les suivants (un vieux "in_progress" rejoué après un
# "completed" ferait reculer la mission). Rejouer est sans danger : le
# backend ne crédite/débite qu'une fois par mission, en se basant sur ses
# transactions (voir backend/app/main.py::update_mission_status et
# update_payment).
MISSION_STATUS_PATH = "/api/bot/missions/status"
PAYMENT_PATH = "/api/bot/payments"


async def flush_backend_outbox() -> bool:
    """Envoie la file dans l'ordre. True si elle est vide à la fin."""
    for entry in get_backend_outbox():
        try:
            await _post_backend(entry["path"], entry["payload"])
        except httpx.HTTPStatusError as error:
            if error.response.status_code < 500:
                # Refus définitif du backend (409 mission déjà réglée, 422...) :
                # le rejouer ne changera rien et bloquerait toute la file.
                logger.warning("Appel backend refusé, retiré de la file : %s %s -> %s", entry["path"], entry["payload"], error)
                delete_backend_outbox_entry(entry["id"])
                continue
            mark_backend_outbox_failure(entry["id"], repr(error))
            return False
        except Exception as error:
            mark_backend_outbox_failure(entry["id"], repr(error))
            return False
        delete_backend_outbox_entry(entry["id"])
    return True


async def _queue_backend_call(path: str, payload: dict) -> bool:
    enqueue_backend_call(path, payload)
    try:
        return await flush_backend_outbox()
    except Exception:
        return False


async def queue_mission_status(mission_id: int, status: str, **kwargs) -> bool:
    """Comme `sync_mission_status_to_backend`, mais rejoué plus tard si le backend ne répond pas."""
    return await _queue_backend_call(MISSION_STATUS_PATH, _mission_status_payload(mission_id, status, **kwargs))


async def queue_payment(quote_id: int, payment_status: str, **kwargs) -> bool:
    """Comme `sync_payment_to_backend`, mais rejoué plus tard si le backend ne répond pas."""
    return await _queue_backend_call(PAYMENT_PATH, _payment_payload(quote_id, payment_status, **kwargs))


def backend_wallet_sync_pending() -> bool:
    """Des mouvements d'argent attendent d'être envoyés au backend : ses
    soldes sont en retard sur db.py, ne pas les afficher."""
    return count_backend_outbox() > 0


async def run_backend_outbox_retry_loop(interval_seconds: float = 60.0):
    while True:
        try:
            await flush_backend_outbox()
        except Exception:
            logger.exception("Rejeu de la file backend en échec")
        await asyncio.sleep(interval_seconds)


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


async def fetch_backend_provider_ranking(telegram_ids: list[int]) -> list[int] | None:
    """Ces prestataires classés par le score backend (vraies notes, missions,
    taux de succès) ; ceux inconnus du backend sont omis. None si le backend
    ne répond pas."""
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
            response = await client.post(
                f"{BACKEND_BASE_URL}/api/bot/providers/rank", json={"telegram_ids": telegram_ids[:100]}
            )
            response.raise_for_status()
            ranked = response.json().get("telegram_ids")
    except Exception:
        return None
    if not isinstance(ranked, list):
        return None
    ranking = []
    for telegram_id in ranked:
        if isinstance(telegram_id, int) and telegram_id not in ranking:
            ranking.append(telegram_id)
    return ranking


BACKEND_UNREACHABLE = "unreachable"


async def backend_mission_payment_status(client_telegram_id: int, mission_id: int) -> str | None:
    """`payment_status` de la mission côté backend ; None si le backend répond
    mais ne connaît pas la mission ; `BACKEND_UNREACHABLE` s'il ne répond pas.
    Sert à détecter l'auto-libération Celery à 24h (backend/app/tasks.py), qui
    paie le prestataire dans Postgres sans que db.py le sache."""
    profile = await fetch_backend_profile(client_telegram_id)
    if not isinstance(profile, dict):
        return BACKEND_UNREACHABLE
    for mission in profile.get("client_missions") or []:
        if isinstance(mission, dict) and mission.get("mission_id") == mission_id:
            return mission.get("payment_status")
    return None


async def backend_mission_already_released(client_telegram_id: int, mission_id: int) -> bool:
    """True seulement si le backend répond et dit que l'escrow est déjà libéré.
    Backend injoignable -> False : l'ouverture d'un litige ne déplace pas
    d'argent, la vérification bloquante se fait au règlement admin."""
    return await backend_mission_payment_status(client_telegram_id, mission_id) == "released"


async def load_profile_from_backend(telegram_id: int, fallback_user: dict | None = None) -> dict:
    backend_profile = await fetch_backend_profile(telegram_id)
    if backend_profile:
        return backend_profile
    # fallback_user vient souvent de db.py (sqlite3.Row, pas de .get()) ; les
    # appelants traitent toujours profile_data["client"] comme un dict.
    client = dict(fallback_user) if fallback_user else {"telegram_id": telegram_id, "first_name": "Client"}
    return {"client": client, "provider": None, "client_missions": [], "provider_missions": []}


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
