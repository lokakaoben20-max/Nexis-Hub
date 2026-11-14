"""Client backend V5 partagé par les flows extraits de `main.py` (Phase 3).

Déplacé depuis `main.py` — regroupe les helpers `sync_*`/`fetch_*` utilisés par
`telegram_bot/registration.py`, `telegram_bot/mission.py` et `telegram_bot/payment.py`.
`main.py` importe les fonctions ci-dessous au lieu de les redéfinir, pour que les
handlers hors scope qui les utilisent encore n'aient rien à changer.

Profils, catalogue, missions, devis et argent n'existent que dans le backend
(CONCEPTION_MISSIONS.md, CONCEPTION_ARGENT.md) : le bot les lit et les demande
ici, au nom de la personne qui écrit (`actor_headers`), et n'en garde aucune
copie. Backend injoignable = `BackendUnavailable`, refus = `MoneyRefused`
avec un code stable : rien n'est écrit ailleurs pour « rattraper plus tard ».
"""

import os

import httpx
from dotenv import load_dotenv

from messages import MESSAGES, get_message

load_dotenv()
BACKEND_BASE_URL = os.getenv("BACKEND_BASE_URL", "http://127.0.0.1:8000")
# Clé de service du canal Telegram (bot et Mini App), différente de celle du
# service WhatsApp : le backend en déduit le canal qui appelle.
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY_TELEGRAM", "")
BACKEND_AUTH_HEADERS = {"X-API-Key": BACKEND_API_KEY}


def check_backend_key() -> None:
    """Refus de démarrer le bot ou la Mini App sans la clé du canal Telegram,
    ou avec l'ancienne clé unique encore dans le `.env` (renommée en
    BACKEND_API_KEY_TELEGRAM, voir backend/app/service_keys.py)."""
    if os.getenv("BACKEND_API_KEY", "").strip():
        raise RuntimeError(
            "BACKEND_API_KEY n'est plus utilisée : renomme-la en BACKEND_API_KEY_TELEGRAM dans le .env"
        )
    if not BACKEND_API_KEY.strip():
        raise RuntimeError("BACKEND_API_KEY_TELEGRAM manquante dans le fichier .env")


def actor_headers(telegram_id: int) -> dict:
    """En-têtes d'une action faite au nom d'une personne : son identité
    Telegram, toujours celle de l'expéditeur du message ou du clic (jamais lue
    dans db.py). Le backend en déduit lui-même le compte Nexis."""
    return {**BACKEND_AUTH_HEADERS, "X-Actor-Channel": "telegram", "X-Actor-Id": str(int(telegram_id))}


async def admin_status(telegram_id: int) -> bool | None:
    """Le backend seul sait qui est admin (rôles en base). Vrai ou faux selon
    sa réponse ; None s'il ne répond pas clairement, ce qui ne donne jamais
    accès aux écrans admin (ils déplacent de l'argent)."""
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=actor_headers(telegram_id)) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/bot/admin/me")
            body = response.json() if response.status_code == 200 else None
    except Exception:
        return None
    answer = body.get("admin") if isinstance(body, dict) else None
    return answer if isinstance(answer, bool) else None


async def admin_telegram_ids() -> list[int]:
    """Admins à prévenir (nouveau prestataire à vérifier). Liste vide si le
    backend ne répond pas."""
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=BACKEND_AUTH_HEADERS) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/bot/admins")
            response.raise_for_status()
            ids = response.json().get("admins")
    except Exception:
        return []
    return [int(value) for value in ids] if isinstance(ids, list) else []


async def _safe_backend_call(coro):
    try:
        return await coro
    except Exception:
        return None


# --- Argent : le backend décide, seul (voir CONCEPTION_ARGENT.md) -----------
# Missions, devis, paiement, démarrage, fin, confirmation, litige et
# résolution vivent dans le backend, seule mémoire (CONCEPTION_MISSIONS.md) :
# le bot n'en garde aucune copie. Backend injoignable ou réponse inattendue =
# `BackendUnavailable` : rien n'a été créé ni payé, l'utilisateur réessaie.


class BackendUnavailable(Exception):
    """Le backend n'a pas répondu, ou pas comme prévu : rien n'a bougé."""


class MoneyRefused(Exception):
    """Refus métier du backend : `code` stable (traduit pour l'utilisateur),
    `mission` = état courant de la mission côté backend, à recopier."""

    def __init__(self, code: str, mission: dict | None = None, money: dict | None = None, details: dict | None = None):
        super().__init__(code)
        self.code = code
        self.mission = mission
        self.money = money
        # Le reste du refus (ex. `attempts_left` d'un mauvais code de présence).
        self.details = details or {}


async def _call(
    method: str, path: str, payload: dict | None = None, actor: int | None = None, expect: tuple[str, ...] = ("mission",)
) -> dict:
    """Une demande au backend. `actor` : identifiant Telegram de la personne
    qui agit (sauf lecture ou relance d'un paiement, qui n'agissent au nom de
    personne). Refus métier = `MoneyRefused(code)` ; injoignable ou réponse
    inattendue (sans aucune des clés `expect`) = `BackendUnavailable`."""
    headers = actor_headers(actor) if actor is not None else BACKEND_AUTH_HEADERS
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            response = await client.request(method, f"{BACKEND_BASE_URL}{path}", json=payload)
    except Exception as error:
        raise BackendUnavailable(repr(error)) from error
    try:
        body = response.json()
    except ValueError as error:
        raise BackendUnavailable(f"réponse illisible ({response.status_code})") from error
    if response.status_code in (400, 403, 404, 409, 503):
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            raise MoneyRefused(detail["code"], detail.get("mission"), detail.get("money"), detail)
    if response.status_code != 200 or not isinstance(body, dict) or not any(key in body for key in expect):
        raise BackendUnavailable(f"réponse inattendue ({response.status_code})")
    return body


async def _money_call(
    method: str, path: str, payload: dict | None = None, actor: int | None = None, expect: str = "mission"
) -> dict:
    body = await _call(method, path, payload, actor, (expect,))
    if not isinstance(body.get(expect), (dict, list)):
        raise BackendUnavailable(f"réponse inattendue (pas de {expect})")
    return body


async def create_mission(client_telegram_id: int, data: dict, creation_key: str) -> dict:
    """Crée la mission dans le backend, qui lui donne son numéro et choisit
    les prestataires prévenus. `creation_key` : la même à chaque nouvel essai
    de la même demande (le backend ne la crée qu'une fois). Renvoie la vue de
    la mission, avec `alerted_provider_telegram_ids` : les seuls à prévenir."""
    media = [{"kind": "photo", "id": file_id} for file_id in data.get("photo_file_ids") or []]
    media += [{"kind": "voice", "id": file_id} for file_id in data.get("voice_file_ids") or []]
    media += [{"kind": "video_note", "id": file_id} for file_id in data.get("video_note_file_ids") or []]
    payload = {
        "creation_key": creation_key,
        "service": data["service"],
        "commune": data["commune"],
        "currency": data.get("currency", "USD"),
        "description": data.get("description", ""),
        "urgent": bool(data.get("urgent", False)),
        "media": media,
        "destination": {
            "latitude": data["destination_latitude"],
            "longitude": data["destination_longitude"],
            "landmark": data["destination_landmark"],
        },
    }
    return await _money_call("POST", "/api/bot/missions", payload, actor=client_telegram_id)


async def get_mission_destination(mission_id: int, telegram_id: int) -> dict:
    """Lieu exact de la mission, si cette personne a le droit de le lire
    (sinon `destination_not_available`, `destination_unknown` ou
    `mission_not_found`)."""
    return await _money_call("GET", f"/api/bot/missions/{mission_id}/destination", actor=telegram_id, expect="destination")


async def get_mission(mission_id: int, telegram_id: int) -> dict:
    """La mission telle que cette personne peut la lire (sinon `mission_not_found`)."""
    return await _money_call("GET", f"/api/bot/missions/{mission_id}", actor=telegram_id)


async def create_quote(mission_id: int, provider_telegram_id: int, amount: float, currency: str, delay_hours: int, message: str = "") -> dict:
    payload = {"mission_id": mission_id, "amount": amount, "currency": currency, "delay_hours": delay_hours, "message": message}
    return await _money_call("POST", "/api/bot/quotes", payload, actor=provider_telegram_id)


async def get_quote(quote_id: int, telegram_id: int) -> dict:
    return await _money_call("GET", f"/api/bot/quotes/{quote_id}", actor=telegram_id)


async def accept_quote(quote_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/quotes/{quote_id}/accept", actor=client_telegram_id)


async def reject_quote(quote_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/quotes/{quote_id}/reject", actor=client_telegram_id)


async def list_my_missions(telegram_id: int, role: str) -> list[dict]:
    """Missions commandées (`client`) ou confiées (`provider`) à cette personne."""
    return (await _money_call("GET", f"/api/me/missions?role={role}", actor=telegram_id, expect="missions"))["missions"]


async def admin_list_missions(admin_telegram_id: int, status: str | None = None) -> list[dict]:
    query = f"?status={status}" if status else ""
    return (await _money_call("GET", f"/api/admin/missions{query}", actor=admin_telegram_id, expect="missions"))["missions"]


async def admin_mission_stats(admin_telegram_id: int) -> dict:
    return (await _money_call("GET", "/api/admin/stats", actor=admin_telegram_id, expect="stats"))["stats"]


async def fund_mission(mission_id: int, quote_id: int, client_telegram_id: int) -> dict:
    """Paie la mission par le wallet (seul paiement direct possible), sur son
    devis accepté : montant et prestataire sont relus par le backend."""
    return await _money_call(
        "POST", f"/api/bot/missions/{mission_id}/fund", {"method": "wallet", "quote_id": quote_id}, actor=client_telegram_id
    )


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


async def create_payment_intent(mission_id: int, quote_id: int, phone: str, operator: str, client_telegram_id: int) -> dict:
    return await _money_call(
        "POST",
        f"/api/bot/missions/{mission_id}/payment-intents",
        {"quote_id": quote_id, "phone": phone, "operator": operator},
        actor=client_telegram_id,
    )


async def refresh_payment_intent(intent_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/payment-intents/{intent_id}/refresh")


async def _payout_call(method: str, path: str, actor: int, payload: dict | None = None, keys=("payout", "payouts")) -> dict:
    """Comme `_money_call`, pour les réponses sans mission : retraits
    (`payout`/`payouts`), liste des montants différents (`intents`)."""
    try:
        async with httpx.AsyncClient(timeout=10.0, headers=actor_headers(actor)) as client:
            if method == "GET":
                response = await client.get(f"{BACKEND_BASE_URL}{path}")
            else:
                response = await client.post(f"{BACKEND_BASE_URL}{path}", json=payload)
        body = response.json()
    except Exception as error:
        raise BackendUnavailable(repr(error)) from error
    if response.status_code in (400, 403, 404, 409, 503):
        detail = body.get("detail") if isinstance(body, dict) else None
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            raise MoneyRefused(detail["code"])
    if response.status_code != 200 or not isinstance(body, dict) or not any(key in body for key in keys):
        raise BackendUnavailable(f"réponse inattendue ({response.status_code})")
    return body


async def app_login_telegram_contact(telegram_id: int, start_token: str, phone: str) -> dict:
    """Connexion à l'application : contact partagé par l'expéditeur après le
    lien de l'app. Rend `{"code": ..., "expires_at": ...}`, ou lève
    `MoneyRefused` avec le code du refus (lien invalide, numéro différent,
    numéro relié à un autre compte)."""
    payload = {"start_token": start_token, "phone": phone}
    return await _payout_call("POST", "/api/bot/app-login/telegram-contact", telegram_id, payload, keys=("code",))


async def app_device_not_me(telegram_id: int, device_id: int) -> dict:
    """« Ce n'est pas moi » : coupe ce téléphone du compte de la personne.
    Rend `{"revoked": True, "already": bool}`, ou lève `MoneyRefused`
    (`device_not_found`)."""
    return await _payout_call("POST", f"/api/bot/app-devices/{device_id}/not-me", telegram_id, {}, keys=("revoked",))


async def admin_revoke_app_devices(admin_telegram_id: int, telegram_id: int) -> dict:
    """L'admin coupe tous les téléphones de l'application de cette personne.
    Rend `{"revoked": n}`."""
    return await _payout_call(
        "POST", "/api/bot/admin/app-devices/revoke", admin_telegram_id, {"telegram_id": telegram_id}, keys=("revoked",)
    )


async def request_payout(telegram_id: int, amount: float, currency: str, phone: str, operator: str) -> dict:
    payload = {"amount": amount, "currency": currency, "phone": phone, "operator": operator}
    return (await _payout_call("POST", "/api/bot/payouts", telegram_id, payload))["payout"]


async def list_payouts_awaiting_approval(admin_telegram_id: int) -> list[dict]:
    return (await _payout_call("GET", "/api/bot/payouts?status=awaiting_approval", admin_telegram_id))["payouts"]


async def decide_payout(payout_id: int, approve: bool, admin_telegram_id: int, reason: str = "") -> dict:
    action = "approve" if approve else "reject"
    return (await _payout_call("POST", f"/api/bot/payouts/{payout_id}/{action}", admin_telegram_id, {"reason": reason}))["payout"]


async def list_payment_mismatches(admin_telegram_id: int) -> list[dict]:
    return (await _payout_call("GET", "/api/bot/payment-intents/mismatches", admin_telegram_id, keys=("intents",)))["intents"]


async def resolve_payment_mismatch(intent_id: int, decision: str, admin_telegram_id: int) -> dict:
    return await _money_call(
        "POST", f"/api/bot/payment-intents/{intent_id}/resolve-mismatch", {"decision": decision}, actor=admin_telegram_id
    )


# Arrivée confirmée : la mission démarre quand le client confirme la présence
# du prestataire, ou quand le prestataire tape le code de présence du client.
# Le backend prévient l'autre partie ; le bot n'affiche que la réponse.


async def declare_arrival(mission_id: int, provider_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/presence/arrived", actor=provider_telegram_id)


async def confirm_presence_code(mission_id: int, provider_telegram_id: int, code: str) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/presence/code", {"code": code}, actor=provider_telegram_id)


async def confirm_presence(mission_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/presence/confirm", actor=client_telegram_id)


async def presence_not_yet(mission_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/presence/not-yet", actor=client_telegram_id)


async def report_wrong_person(mission_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/presence/wrong-person", actor=client_telegram_id)


async def finish_mission(mission_id: int, provider_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/finish", actor=provider_telegram_id)


async def confirm_mission(mission_id: int, client_telegram_id: int) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/confirm", actor=client_telegram_id)


async def open_dispute(mission_id: int, client_telegram_id: int, reason: str) -> dict:
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/dispute", {"reason": reason}, actor=client_telegram_id)


async def decide_dispute(mission_id: int, decision: str, admin_telegram_id: int, provider_percentage: float | None = None) -> dict:
    """Décision de Nexis Hub sur un litige. La première attend 3 jours avant
    d'être exécutée ; la révision d'une décision contestée est exécutée tout
    de suite. Le backend prévient lui-même le client et le prestataire."""
    return await _money_call(
        "POST",
        f"/api/bot/missions/{mission_id}/dispute/decide",
        {"decision": decision, "provider_percentage": provider_percentage},
        actor=admin_telegram_id,
    )


async def contest_dispute(mission_id: int, telegram_id: int, reason: str) -> dict:
    """Le client ou le prestataire conteste la première décision."""
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/dispute/contest", {"reason": reason}, actor=telegram_id)


async def propose_dispute_settlement(mission_id: int, client_telegram_id: int, kind: str, provider_percentage: float | None = None) -> dict:
    """Le client propose un accord amiable. Le backend prévient lui-même le
    prestataire, avec les boutons pour répondre."""
    return await _money_call(
        "POST",
        f"/api/bot/missions/{mission_id}/dispute/offers",
        {"kind": kind, "provider_percentage": provider_percentage},
        actor=client_telegram_id,
    )


async def answer_dispute_settlement(mission_id: int, offer_id: int, provider_telegram_id: int, accept: bool) -> dict:
    """Le prestataire accepte ou refuse. Le backend prévient lui-même le client."""
    action = "accept" if accept else "decline"
    return await _money_call("POST", f"/api/bot/missions/{mission_id}/dispute/offers/{offer_id}/{action}", actor=provider_telegram_id)


async def fetch_wallets(telegram_id: int) -> dict | None:
    """Wallet de la personne (un seul, qu'elle soit cliente, prestataire ou
    les deux), lu dans le registre. None si le backend ne répond pas : l'écran
    affiche alors « solde indisponible », jamais un chiffre local. Toujours
    le wallet de la personne qui regarde (`telegram_id` = l'expéditeur)."""
    try:
        async with httpx.AsyncClient(timeout=5.0, headers=actor_headers(telegram_id)) as client:
            response = await client.get(f"{BACKEND_BASE_URL}/api/me/wallet")
            response.raise_for_status()
            body = response.json()
    except Exception:
        return None
    return body if isinstance(body, dict) else None


def money_failure_text(mission_id: int, error: Exception, lang: str, unavailable_key: str = "money_backend_unavailable") -> str:
    """Message à montrer quand une demande au backend n'a pas abouti.
    `unavailable_key` : texte « service indisponible » adapté à la demande
    (paiement par défaut ; `service_unavailable` hors argent)."""
    if isinstance(error, MoneyRefused):
        key = f"money_error_{error.code}"
        return get_message(key if key in MESSAGES["fr"] else "money_error_generic", lang)
    return get_message(unavailable_key, lang)


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
        "rating": rating,
        "comment": comment,
    }
    async with httpx.AsyncClient(timeout=5.0, headers=actor_headers(client_telegram_id)) as client:
        response = await client.post(f"{BACKEND_BASE_URL}/api/bot/reviews", json=payload)
        response.raise_for_status()
        return response.json()


async def get_state_language(state) -> str:
    data = await state.get_data()
    return data.get("language", "fr")


# --- Profils : au nom de la personne qui écrit (routes /api/me/*) ------------


LANGUAGES = ("fr", "ln", "en")


def telegram_language(person) -> str:
    """Langue que Telegram donne pour la personne (`language_code`), réduite
    aux langues de Nexis ; « fr » sinon. Seulement pour une personne que le
    backend ne connaît pas encore, ou quand il ne répond pas."""
    code = (getattr(person, "language_code", None) or "").lower()[:2]
    return code if code in LANGUAGES else "fr"


async def get_language(person) -> str:
    """Langue dans laquelle écrire à cette personne : celle de son compte
    Nexis. `person` : l'utilisateur Telegram qui écrit (`from_user`) ou
    l'identifiant Telegram de l'autre partie d'une mission. Personne inconnue
    du backend, ou backend injoignable : la langue de son Telegram si on
    l'a, sinon « fr » ; la demande qui suit, elle, échouera proprement."""
    telegram_id = person if isinstance(person, int) else person.id
    try:
        body = await _call("GET", f"/api/bot/telegram/{int(telegram_id)}/language", expect=("language",))
    except (BackendUnavailable, MoneyRefused):
        return telegram_language(person)
    language = body.get("language")
    return language if language in LANGUAGES else telegram_language(person)


async def fetch_catalogue() -> dict:
    """Services actifs (noms en trois langues) et communes servies."""
    return await _call("GET", "/api/services", expect=("services",))


async def fetch_me(telegram_id: int) -> dict:
    """Profil de la personne : `client`, `provider` (ou None), `language`,
    `profile_type` (client, provider, guest)."""
    return await _call("GET", "/api/me/profile", actor=telegram_id, expect=("profile_type",))


async def my_profile(telegram_id: int) -> dict | None:
    """Comme `fetch_me`, ou None si le backend ne répond pas (l'écran dit
    alors « service indisponible », jamais un profil inventé)."""
    try:
        return await fetch_me(telegram_id)
    except (BackendUnavailable, MoneyRefused):
        return None


async def save_client_profile(
    telegram_id: int, first_name: str, phone_number: str | None, language: str, phone_verified: bool = False
) -> dict:
    """Inscription du client. `phone_verified` : seulement pour un numéro
    reçu par « Partager mon numéro », contact de l'expéditeur."""
    payload = {"first_name": first_name, "phone_number": phone_number, "language": language, "phone_verified": phone_verified}
    return await _call("PUT", "/api/me/client-profile", payload, actor=telegram_id, expect=("profile_type",))


async def save_provider_profile(telegram_id: int, data: dict) -> dict:
    """Inscription du prestataire (documents compris). Le backend le met en
    attente de vérification par l'équipe."""
    return await _call("PUT", "/api/me/provider-profile", data, actor=telegram_id, expect=("profile_type",))


async def set_my_language(telegram_id: int, language: str) -> dict:
    return await _call("PATCH", "/api/me/language", {"language": language}, actor=telegram_id, expect=("profile_type",))


async def set_my_name(telegram_id: int, first_name: str) -> dict:
    return await _call("PATCH", "/api/me/name", {"first_name": first_name}, actor=telegram_id, expect=("profile_type",))


async def set_my_services(telegram_id: int, services: list[str]) -> dict:
    return await _call(
        "PUT", "/api/me/provider-profile/services", {"services": services}, actor=telegram_id, expect=("profile_type",)
    )


async def set_my_availability(telegram_id: int, status: str) -> dict:
    """`available` ou `offline` ; refus `provider_not_verified`,
    `provider_suspended`."""
    return await _call("PATCH", "/api/me/provider-profile/status", {"status": status}, actor=telegram_id, expect=("profile_type",))


async def decline_alert(mission_id: int, provider_telegram_id: int) -> dict:
    """« Pas disponible » sur une alerte : compté une fois par alerte ;
    `paused_now` au 3e refus d'affilée."""
    return await _call("POST", f"/api/bot/missions/{mission_id}/decline", actor=provider_telegram_id, expect=("counted",))


async def propose_service(provider_telegram_id: int, service_name: str, description: str) -> dict:
    body = await _call(
        "POST",
        "/api/bot/service-requests",
        {"service_name": service_name, "description": description},
        actor=provider_telegram_id,
        expect=("service_request",),
    )
    return body["service_request"]


async def my_service_requests(provider_telegram_id: int) -> list[dict]:
    body = await _call("GET", "/api/me/service-requests", actor=provider_telegram_id, expect=("service_requests",))
    return body["service_requests"]


# --- Admin : profils et propositions de service ------------------------------
# Le backend revérifie que la personne est admin (`not_admin` sinon).


async def admin_providers(admin_telegram_id: int, status: str | None = None) -> list[dict]:
    query = f"?status={status}" if status else ""
    return (await _call("GET", f"/api/admin/providers{query}", actor=admin_telegram_id, expect=("providers",)))["providers"]


async def admin_decide_provider(admin_telegram_id: int, account_id: int, action: str) -> dict:
    """`action` : verify, reject, suspend ou unsuspend. Rend le profil."""
    if action not in ("verify", "reject", "suspend", "unsuspend"):
        raise ValueError(action)
    body = await _call("POST", f"/api/admin/providers/{int(account_id)}/{action}", actor=admin_telegram_id, expect=("provider",))
    return body["provider"]


async def admin_clients(admin_telegram_id: int) -> list[dict]:
    return (await _call("GET", "/api/admin/clients", actor=admin_telegram_id, expect=("clients",)))["clients"]


async def admin_service_requests(admin_telegram_id: int) -> list[dict]:
    body = await _call("GET", "/api/admin/service-requests", actor=admin_telegram_id, expect=("service_requests",))
    return body["service_requests"]


async def admin_decide_service_request(admin_telegram_id: int, request_id: int, status: str, admin_note: str) -> dict:
    """Une seule décision par proposition : `already_reviewed` ensuite."""
    body = await _call(
        "PATCH",
        f"/api/admin/service-requests/{int(request_id)}",
        {"status": status, "admin_note": admin_note},
        actor=admin_telegram_id,
        expect=("service_request",),
    )
    return body["service_request"]
