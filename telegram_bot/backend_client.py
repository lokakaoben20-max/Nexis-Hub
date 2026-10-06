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

from db import apply_backend_mission, create_user, get_mission_by_id, get_provider_by_telegram_id, get_user_by_telegram_id
from messages import MESSAGES, get_message

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


# --- Argent : le backend décide, seul (voir CONCEPTION_ARGENT.md) -----------
# Paiement, démarrage, fin, confirmation, litige et résolution sont des
# demandes au registre du backend. Le bot n'écrit l'état dans db.py qu'après
# la réponse du backend (`db.apply_backend_mission`), jamais avant. Backend
# injoignable ou réponse inattendue = `BackendUnavailable` : aucune action
# d'argent n'a eu lieu, l'utilisateur réessaie.


class BackendUnavailable(Exception):
    """Le backend n'a pas répondu, ou pas comme prévu : rien n'a bougé."""


class MoneyRefused(Exception):
    """Refus métier du backend : `code` stable (traduit pour l'utilisateur),
    `mission` = état courant de la mission côté backend, à recopier."""

    def __init__(self, code: str, mission: dict | None = None, money: dict | None = None):
        super().__init__(code)
        self.code = code
        self.mission = mission
        self.money = money


async def _money_call(method: str, path: str, payload: dict | None = None) -> dict:
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=BACKEND_AUTH_HEADERS) as client:
            if method == "GET":
                response = await client.get(f"{BACKEND_BASE_URL}{path}")
            else:
                response = await client.post(f"{BACKEND_BASE_URL}{path}", json=payload)
    except Exception as error:
        raise BackendUnavailable(repr(error)) from error
    try:
        body = response.json()
    except ValueError as error:
        raise BackendUnavailable(f"réponse illisible ({response.status_code})") from error
    if response.status_code in (400, 403, 404, 409):
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            raise MoneyRefused(detail["code"], detail.get("mission"), detail.get("money"))
    if response.status_code != 200 or not isinstance(body, dict) or not isinstance(body.get("mission"), dict):
        raise BackendUnavailable(f"réponse inattendue ({response.status_code})")
    return body


async def fund_mission(mission, quote, method: str) -> dict:
    """Paie la mission en escrow par le wallet (seul paiement direct possible).
    `mission` et `quote` sont les lignes db.py : la demande porte tout ce dont
    le backend a besoin."""
    return await _money_call("POST", f"/api/bot/missions/{mission['id']}/fund", _funding_payload(mission, quote, method))


def _funding_payload(mission, quote, method: str) -> dict:
    return {
        "method": method,
        "client_telegram_id": mission["client_telegram_id"],
        "provider_telegram_id": quote["provider_telegram_id"],
        "quote_ref": quote["id"],
        "amount": quote["amount"],
        "currency": quote["currency"],
        "urgent": bool(mission["is_urgent"]),
        "service": mission["service"],
        "commune": mission["commune"],
        "description": mission["description"] or "",
    }


# --- Mobile Money réel (CONCEPTION_MOBILE_MONEY.md) --------------------------
# Un paiement Mobile Money n'existe que confirmé par l'agrégateur : le bot
# ouvre une intention de paiement et en affiche le statut, rien de plus.

OPERATORS = ("mpesa", "airtel", "orange")
# Préfixes des opérateurs en RDC (après +243).
_OPERATOR_PREFIXES = {"81": "mpesa", "82": "mpesa", "83": "mpesa", "97": "airtel", "98": "airtel", "99": "airtel",
                      "80": "orange", "84": "orange", "85": "orange", "89": "orange"}


def normalize_phone(raw) -> str | None:
    """Numéro RDC au format +243XXXXXXXXX, ou None s'il n'en est pas un."""
    digits = "".join(ch for ch in str(raw or "") if ch.isdigit())
    if digits.startswith("243"):
        digits = digits[3:]
    elif digits.startswith("0"):
        digits = digits[1:]
    return f"+243{digits}" if len(digits) == 9 else None


def detect_operator(phone: str | None) -> str | None:
    return _OPERATOR_PREFIXES.get(phone[4:6]) if phone else None


async def create_payment_intent(mission, quote, phone: str, operator: str) -> dict:
    return await _money_call(
        "POST",
        f"/api/bot/missions/{mission['id']}/payment-intents",
        {**_funding_payload(mission, quote, "mobile_money"), "phone": phone, "operator": operator},
    )


async def refresh_payment_intent(intent_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/payment-intents/{intent_id}/refresh")


async def _payout_call(method: str, path: str, payload: dict | None = None) -> dict:
    """Comme `_money_call`, pour les retraits (réponse `payout`/`payouts`)."""
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=BACKEND_AUTH_HEADERS) as client:
            if method == "GET":
                response = await client.get(f"{BACKEND_BASE_URL}{path}")
            else:
                response = await client.post(f"{BACKEND_BASE_URL}{path}", json=payload)
        body = response.json()
    except Exception as error:
        raise BackendUnavailable(repr(error)) from error
    if response.status_code in (400, 403, 404, 409):
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            raise MoneyRefused(detail["code"])
    if response.status_code != 200 or not isinstance(body, dict) or not ("payout" in body or "payouts" in body):
        raise BackendUnavailable(f"réponse inattendue ({response.status_code})")
    return body


async def request_payout(telegram_id: int, amount: float, currency: str, phone: str, operator: str) -> dict:
    payload = {"telegram_id": telegram_id, "amount": amount, "currency": currency, "phone": phone, "operator": operator}
    return (await _payout_call("POST", "/api/bot/payouts", payload))["payout"]


async def list_payouts_awaiting_approval() -> list[dict]:
    return (await _payout_call("GET", "/api/bot/payouts?status=awaiting_approval"))["payouts"]


async def decide_payout(payout_id: int, approve: bool, admin_telegram_id: int, reason: str = "") -> dict:
    action = "approve" if approve else "reject"
    payload = {"admin_telegram_id": admin_telegram_id, "reason": reason}
    return (await _payout_call("POST", f"/api/bot/payouts/{payout_id}/{action}", payload))["payout"]


async def start_mission(mission_id: int, provider_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/start", {"provider_telegram_id": provider_telegram_id})


async def finish_mission(mission_id: int, provider_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/finish", {"provider_telegram_id": provider_telegram_id})


async def confirm_mission(mission_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/confirm", {"client_telegram_id": client_telegram_id})


async def open_dispute(mission_id: int, client_telegram_id: int, reason: str) -> dict:
    return await _money_call(
        "POST", f"/api/bot/missions/{mission_id}/dispute", {"client_telegram_id": client_telegram_id, "reason": reason}
    )


async def resolve_dispute(mission_id: int, decision: str, admin_telegram_id: int, provider_percentage: float | None = None) -> dict:
    return await _money_call(
        "POST",
        f"/api/bot/missions/{mission_id}/dispute/resolve",
        {"decision": decision, "admin_telegram_id": admin_telegram_id, "provider_percentage": provider_percentage},
    )


async def fetch_wallets(telegram_id: int) -> dict | None:
    """Wallet de la personne (un seul, qu'elle soit cliente, prestataire ou
    les deux), lu dans le registre. None si le backend ne répond pas : l'écran
    affiche alors « solde indisponible », jamais un chiffre local."""
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/bot/wallets/{telegram_id}")
            response.raise_for_status()
            body = response.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def money_failure_text(mission_id: int, error: Exception, lang: str) -> str:
    """Message à montrer quand une action d'argent n'a pas abouti. Sur un refus
    du backend, recopie d'abord l'état réel de la mission dans db.py."""
    if isinstance(error, MoneyRefused):
        if isinstance(error.mission, dict):
            apply_backend_mission(mission_id, error.mission)
        key = f"money_error_{error.code}"
        return get_message(key if key in MESSAGES["fr"] else "money_error_generic", lang)
    return get_message("money_backend_unavailable", lang)


def wallet_balance(wallets: dict | None, currency: str) -> float | None:
    """Solde dans une devise, ou None si inconnu (backend injoignable)."""
    entity = (wallets or {}).get("wallet")
    if not isinstance(entity, dict):
        return None
    value = entity.get("wallet_balance_usd" if currency == "USD" else "wallet_balance_cdf")
    return float(value) if isinstance(value, (int, float)) else None


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
